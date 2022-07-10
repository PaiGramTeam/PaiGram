import os
import time
from io import BytesIO
from typing import Optional, List

import httpx
import ujson
from PIL import Image, ImageMath

from model.helpers import REQUEST_HEADERS

Image.MAX_IMAGE_PIXELS = None

ZOOM = 0.5
RESOURCE_ICON_OFFSET = (-int(150 * 0.5 * ZOOM), -int(150 * ZOOM))


class MapHelper:
    LABEL_URL = 'https://api-static.mihoyo.com/common/blackboard/ys_obc/v1/map/label/tree?app_sn=ys_obc'
    POINT_LIST_URL = 'https://api-static.mihoyo.com/common/blackboard/ys_obc/v1/map/point/list?map_id=2&app_sn=ys_obc'
    MAP_URL = 'https://api-static.mihoyo.com/common/map_user/ys_obc/v1/map/info?map_id=2&app_sn=ys_obc&lang=zh-cn'

    def __init__(self, cache_dir_name: str = "cache"):
        self._current_dir = os.getcwd()
        self._output_dir = os.path.join(self._current_dir, cache_dir_name)
        self._resources_icon_dir = os.path.join(self._current_dir, "resources", "icon")
        self._map_dir = os.path.join(self._resources_icon_dir, "map_icon.jpg")
        self.client = httpx.AsyncClient(headers=REQUEST_HEADERS, timeout=10.0)
        self.all_resource_type: dict = {}
        """这个字典保存所有资源类型

        "1": {
            "id": 1,
            "name": "传送点",
            "icon": "",
            "parent_id": 0,
            "depth": 1,
            "node_type": 1,
            "jump_type": 0,
            "jump_target_id": 0,
            "display_priority": 0,
            "children": []
        }
        """
        self.can_query_type_list: dict = {}
        """这个字典保存所有可以查询的资源类型名称和ID，这个字典只有名称和ID

        上边字典里"depth": 2的类型才可以查询，"depth": 1的是1级目录，不能查询
        
        "七天神像":"2"
        
        "风神瞳":"5"
        """
        self.all_resource_point_list: list = []
        """这个列表保存所有资源点的数据

        {
            "id": 2740,
            "label_id": 68,
            "x_pos": -1789,
            "y_pos": 2628,
            "author_name": "作者名称",
            "ctime": "更新时间",
            "display_state": 1
        }
        """
        self.date: str = ""
        """记录上次更新"all_resource_point_list"的日期
        """

        self.center: Optional[List[float]] = None
        """center
        """

        self.map_icon: Optional[Image] = None
        """map_icon
        """

    async def download_icon(self, url):
        """下载图片 返回Image对象
        :param url:
        :return:
        """
        resp = await self.client.get(url=url)
        if resp.status_code != 200:
            raise ValueError(f"获取图片数据失败，错误代码 {resp.status_code}")
        icon = resp.content
        return Image.open(BytesIO(icon))

    async def download_json(self, url):
        """
        获取资源数据，返回 JSON
        :param url:
        :return: dict
        """
        resp = await self.client.get(url=url)
        if resp.status_code != 200:
            raise RuntimeError(f"获取资源点数据失败，错误代码 {resp.status_code}")
        return resp.json()

    async def init_point_list_and_map(self):
        await self.up_label_and_point_list()
        await self.up_map()

    async def up_map(self):
        """更新地图文件 并按照资源点的范围自动裁切掉不需要的地方
        裁切地图需要最新的资源点位置，所以要先调用 up_label_and_point_list 再更新地图
        :return: None
        """
        map_info = await self.download_json(self.MAP_URL)
        map_info = map_info["data"]["info"]["detail"]
        map_info = ujson.loads(map_info)

        map_url_list = map_info['slices'][0]
        origin = map_info["origin"]

        x_start = map_info['total_size'][1]
        y_start = map_info['total_size'][1]
        x_end = 0
        y_end = 0
        for resource_point in self.all_resource_point_list:
            x_pos = resource_point["x_pos"] + origin[0]
            y_pos = resource_point["y_pos"] + origin[1]
            x_start = min(x_start, x_pos)
            y_start = min(y_start, y_pos)
            x_end = max(x_end, x_pos)
            y_end = max(y_end, y_pos)

        x_start -= 200
        y_start -= 200
        x_end += 200
        y_end += 200

        self.center = [origin[0] - x_start, origin[1] - y_start]
        x = int(x_end - x_start)
        y = int(y_end - y_start)
        self.map_icon = Image.new("RGB", (x, y))
        x_offset = 0
        for i in map_url_list:
            map_url = i["url"]
            map_icon = await self.download_icon(map_url)
            self.map_icon.paste(map_icon, (int(-x_start) + x_offset, int(-y_start)))
            x_offset += map_icon.size[0]

    async def up_label_and_point_list(self):
        """更新label列表和资源点列表
        :return:
        """
        label_data = await self.download_json(self.LABEL_URL)
        for label in label_data["data"]["tree"]:
            self.all_resource_type[str(label["id"])] = label
            for sublist in label["children"]:
                self.all_resource_type[str(sublist["id"])] = sublist
                self.can_query_type_list[sublist["name"]] = str(sublist["id"])
                await self.up_icon_image(sublist)
            label["children"] = []
        test = await self.download_json(self.POINT_LIST_URL)
        self.all_resource_type = test["data"]["point_list"]
        self.date = time.strftime("%d")

    async def up_icon_image(self, sublist: dict):
        """检查是否有图标，没有图标下载保存到本地
        :param sublist:
        :return:
        """
        icon_id = sublist["id"]
        icon_path = os.path.join(self._resources_icon_dir, f"{icon_id}.png")

        if not os.path.exists(icon_path):
            icon_url = sublist["icon"]
            icon = await self.download_icon(icon_url)
            icon = icon.resize((150, 150))

            box_alpha = Image.open(
                os.path.join(os.path.dirname(__file__), os.path.pardir,
                             "resources", "icon", "box_alpha.png")).getchannel("A")
            box = Image.open(os.path.join(os.path.dirname(__file__), os.path.pardir, "resources", "icon", "box.png"))

            try:
                icon_alpha = icon.getchannel("A")
                icon_alpha = ImageMath.eval("convert(a*b/256, 'L')", a=icon_alpha, b=box_alpha)
            except ValueError:
                # 米游社的图有时候会没有alpha导致报错，这时候直接使用box_alpha当做alpha就行
                icon_alpha = box_alpha

            icon2 = Image.new("RGBA", (150, 150), "#00000000")
            icon2.paste(icon, (0, -10))

            bg = Image.new("RGBA", (150, 150), "#00000000")
            bg.paste(icon2, mask=icon_alpha)
            bg.paste(box, mask=box)

            with open(icon_path, "wb") as icon_file:
                bg.save(icon_file)

    async def get_resource_map_mes(self, name):
        if self.date != time.strftime("%d"):
            await self.init_point_list_and_map()
        if name not in self.can_query_type_list:
            return f"派蒙还不知道 {name} 在哪里呢，可以发送 `/map list` 查看资源列表"
        resource_id = self.can_query_type_list[name]
        map_res = ResourceMap(self.all_resource_point_list, self.map_icon, self.center, resource_id)
        count = map_res.get_resource_count()
        if not count:
            return f"派蒙没有找到 {name} 的位置，可能米游社wiki还没更新"
        map_res.gen_jpg()
        mes = f"派蒙一共找到 {name} 的 {count} 个位置点\n* 数据来源于米游社wiki"
        return mes

    def get_resource_list_mes(self):
        temp = {}
        for list_id in self.all_resource_type:
            # 先找1级目录
            if self.all_resource_type[list_id]["depth"] == 1:
                temp[list_id] = []
        for list_id in self.all_resource_type:
            # 再找2级目录
            if self.all_resource_type[list_id]["depth"] == 2:
                temp[str(self.all_resource_type[list_id]["parent_id"])].append(list_id)
        mes = "当前资源列表如下：\n"

        for resource_type_id in temp:
            if resource_type_id in ["1", "12", "50", "51", "95", "131"]:
                # 在游戏里能查到的数据这里就不列举了，不然消息太长了
                continue
            mes += f"{self.all_resource_type[resource_type_id]['name']}："
            for resource_id in temp[resource_type_id]:
                mes += f"{self.all_resource_type[resource_id]['name']}，"
            mes += "\n"
        return mes


class ResourceMap:

    def __init__(self, all_resource_point_list: List[dict], map_icon: Image, center: List[float], resource_id: int):
        self.all_resource_point_list = all_resource_point_list
        self.resource_id = resource_id
        self.center = center
        self.map_image = map_icon.copy()
        self.map_size = self.map_image.size
        # 地图要要裁切的左上角和右下角坐标
        # 这里初始化为地图的大小
        self.x_start = self.map_size[0]
        self.y_start = self.map_size[1]
        self.x_end = 0
        self.y_end = 0
        resource_icon = Image.open(self.get_icon_path())
        self.resource_icon = resource_icon.resize((int(150 * ZOOM), int(150 * ZOOM)))
        self.resource_xy_list = self.get_resource_point_list()

    def get_icon_path(self):
        # 检查有没有图标，有返回正确图标，没有返回默认图标
        icon_path = os.path.join(os.path.dirname(__file__), os.path.pardir,
                                 "resources", "icon", f"{self.resource_id}.png")
        if os.path.exists(icon_path):
            return icon_path
        return os.path.join(os.path.dirname(__file__), os.path.pardir, "resources", "icon", "0.png")

    def get_resource_point_list(self):
        temp_list = []
        for resource_point in self.all_resource_point_list:
            if str(resource_point["label_id"]) == self.resource_id:
                # 获取xy坐标，然后加上中心点的坐标完成坐标转换
                x = resource_point["x_pos"] + self.center[0]
                y = resource_point["y_pos"] + self.center[1]
                temp_list.append((int(x), int(y)))
        return temp_list

    def paste(self):
        for x, y in self.resource_xy_list:
            # 把资源图片贴到地图上
            # 这时地图已经裁切过了，要以裁切后的地图左上角为中心再转换一次坐标
            x -= self.x_start
            y -= self.y_start
            self.map_image.paste(self.resource_icon, (x + RESOURCE_ICON_OFFSET[0], y + RESOURCE_ICON_OFFSET[1]),
                                 self.resource_icon)

    def crop(self):
        # 把大地图裁切到只保留资源图标位置
        for x, y in self.resource_xy_list:
            # 找出4个方向最远的坐标，用于后边裁切
            self.x_start = min(x, self.x_start)
            self.y_start = min(y, self.y_start)
            self.x_end = max(x, self.x_end)
            self.y_end = max(y, self.y_end)

        # 先把4个方向扩展150像素防止把资源图标裁掉
        self.x_start -= 150
        self.y_start -= 150
        self.x_end += 150
        self.y_end += 150

        # 如果图片裁切得太小会看不出资源的位置在哪，检查图片裁切的长和宽看够不够1000，不到1000的按1000裁切
        if (self.x_end - self.x_start) < 1000:
            center = int((self.x_end + self.x_start) / 2)
            self.x_start = center - 500
            self.x_end = center + 500
        if (self.y_end - self.y_start) < 1000:
            center = int((self.y_end + self.y_start) / 2)
            self.y_start = center - 500
            self.y_end = center + 500

        self.map_image = self.map_image.crop((self.x_start, self.y_start,
                                              self.x_end, self.y_end))

    def gen_jpg(self):
        if not self.resource_xy_list:
            return "没有这个资源的信息"
        if os.path.exists("temp"):
            pass
        else:
            os.mkdir("temp")  # 查找 temp 目录 (缓存目录) 是否存在，如果不存在则创建
        self.crop()
        self.paste()
        self.map_image.save(f'temp{os.sep}map.jpg', format='JPEG')

    def get_resource_count(self):
        return len(self.resource_xy_list)
