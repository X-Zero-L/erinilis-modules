import re
from pathlib import Path
import nonebot
from bs4 import BeautifulSoup
from nonebot import MessageSegment, get_bot
from ..imghandler import *
from ..util import config, filter_list, get_font, get_path, init_db, pil2b64
from .main import ann

assets_dir = Path(get_path('assets')) / 'ann'

list_head = Image.open(assets_dir / "list.png")
list_item = Image.open(assets_dir / "item.png").resize((384, 96)).convert("RGBA")

w65 = get_font(26, w=65)


async def ann_list_card():
    ann_list = await ann().get_ann_list()
    if not ann_list:
        raise Exception('获取游戏公告失败,请检查接口是否正常')

    height_len = max(len(ann_list[0]['list']), len(ann_list[1]['list']))

    bg = Image.new('RGBA',
                   (list_head.width,
                    list_head.height + list_item.height * height_len + 20 + 30),
                   '#f9f6f2')
    easy_paste(bg, list_head, (0 ,0))

    for data in ann_list:
        x = 45
        if data['type_id'] == 1:
            x = 472

        for index, ann_info in enumerate(data['list']):
            new_item = list_item.copy()
            subtitle = ann_info['subtitle']
            draw_text_by_line(new_item, (0, 30 - (len(subtitle) > 10 and 10 or 0)), subtitle, get_font(25), '#3b4354', 250, True)

            draw_text_by_line(new_item, (new_item.width - 80, 10), str(ann_info['ann_id']), get_font(18), '#3b4354', 100)

            bg = easy_alpha_composite(bg, new_item, (x, list_head.height + (index * new_item.height)))

    tip = '*可以使用 原神公告#0000(右上角ID) 来查看详细内容, 例子: 原神公告#2434'
    draw_text_by_line(bg, (0, bg.height - 35), tip, get_font(18), '#767779', 1000, True)

    return pil2b64(bg)

async def ann_detail_card(ann_id):
    ann_list = await ann().get_ann_content()
    if not ann_list:
        raise Exception('获取游戏公告失败,请检查接口是否正常')
    content = filter_list(ann_list, lambda x: x['ann_id'] == ann_id)
    if not content:
        raise Exception(f'没有找到对应的公告ID :{ann_id}')
    soup = BeautifulSoup(content[0]['content'], 'lxml')
    banner = content[0]['banner']
    ann_img = banner or ''
    for a in soup.find_all('a'):
        # href = a.get('href')
        # a.string += ' (%s)' % re.search(r'https?.+', re.sub(r'[;()\']', '', href)).group()
        a.string = ''

    for img in soup.find_all('img'):
        img.string = img.get('src')

    msg_list = [ann_img]
    msg_list += [BeautifulSoup(x.get_text('').replace('<<', ''), 'lxml').get_text() + '\n' for x in soup.find_all('p')]


    drow_height = 0
    for msg in msg_list:
        if msg.strip().endswith(('jpg', 'png')):
            img = await get_pic(msg.strip())
            img_height = img.size[1]
            if img.width > 1080:
                img_height = int(img.height * 0.6)
            drow_height += img_height + 40
        else:
            x_drow_duanluo, x_drow_note_height, x_drow_line_height, x_drow_height = split_text(msg)
            drow_height += x_drow_height

    im = Image.new("RGB", (1080, drow_height), '#f9f6f2')
    draw = ImageDraw.Draw(im)
    # 左上角开始
    x, y = 0, 0
    for msg in msg_list:
        if msg.strip().endswith(('jpg', 'png')):
            img = await get_pic(msg.strip())
            if img.width > im.width:
                img = img.resize((int(img.width * 0.6), int(img.height * 0.6)))
            easy_paste(im, img, (0, y))
            y += img.size[1] + 40
        else:
            drow_duanluo, drow_note_height, drow_line_height, drow_height = split_text(msg)
            for duanluo, line_count in drow_duanluo:
                draw.text((x, y), duanluo, fill=(0, 0, 0), font=w65)
                y += drow_line_height * line_count

    _x, _y = w65.getsize("囗")
    padding = (_x, _y, _x, _y)
    im = ImageOps.expand(im, padding, '#f9f6f2')

    return pil2b64(im)


def split_text(content):
    # 按规定宽度分组
    max_line_height, total_lines = 0, 0
    allText = []
    for text in content.split('\n'):
        duanluo, line_height, line_count = get_duanluo(text)
        max_line_height = max(line_height, max_line_height)
        total_lines += line_count
        allText.append((duanluo, line_count))
    line_height = max_line_height
    total_height = total_lines * line_height
    drow_height = total_lines * line_height
    return allText, total_height, line_height, drow_height

def get_duanluo(text):
    txt = Image.new('RGBA', (600, 800), (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt)
    # 所有文字的段落
    duanluo = ""
    max_width = 1080
    # 宽度总和
    sum_width = 0
    # 几行
    line_count = 1
    # 行高
    line_height = 0
    for char in text:
        width, height = draw.textsize(char, w65)
        sum_width += width
        if sum_width > max_width: # 超过预设宽度就修改段落 以及当前行数
            line_count += 1
            sum_width = 0
            duanluo += '\n'
        duanluo += char
        line_height = max(height, line_height)
    if not duanluo.endswith('\n'):
        duanluo += '\n'
    return duanluo, line_height, line_count



ann_db = init_db(config.cache_dir, 'ann.sqlite')


def sub_ann(group):
    sub_list = ann_db.get('sub', [])
    sub_list.append(group)
    ann_db['sub'] = list(set(sub_list))
    return '成功订阅原神公告'


def unsub_ann(group):
    sub_list = ann_db.get('sub', [])
    sub_list.remove(group)
    ann_db['sub'] = sub_list
    return '成功取消订阅原神公告'


async def check_ann_state():
    # print('定时任务: 原神公告查询..')
    ids = ann_db.get('ids', [])
    sub_list = ann_db.get('sub', [])
    if not sub_list:
        # print('没有群订阅, 取消获取数据')
        return
    if not ids:
        ids = await ann().get_ann_ids()
        if not ids:
            raise Exception('获取原神公告ID列表错误,请检查接口')
        ann_db['ids'] = ids
        print('初始成功, 将在下个轮询中更新.')
        return
    new_ids = await ann().get_ann_ids()

    new_ann = set(ids) ^ set(new_ids)
    if not new_ann:
        # print('没有最新公告')
        return

    detail_list = []
    for ann_id in new_ann:
        if ann_id in config.setting.ann_block:
            continue
        try:
            img = await ann_detail_card(ann_id)
            detail_list.append(MessageSegment.image(img))
        except Exception as e:
            print(e)


    # print('推送完毕, 更新数据库')
    ann_db['ids'] = new_ids

    for group in sub_list:
        for msg in detail_list:
            try:
                bot = get_bot()
                await bot.send_group_msg(group_id=group, message=msg)
            except Exception as e:
                print(e)


if config.setting.ann_cron_enable:
    @nonebot.scheduler.scheduled_job('cron',minute=f"*/{config.setting.ann_cron_time}" )
    async def _():
        await check_ann_state()
