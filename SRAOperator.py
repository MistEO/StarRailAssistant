import io
import time

import cv2
import pyautogui
import pygetwindow
import pyscreeze
from PIL import Image
from selenium.webdriver import ActionChains
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.webdriver import WebDriver

from StarRailAssistant.Exceptions import WindowNoFoundException, MultipleWindowsException, MatchFailureError, \
    WindowInactiveException
from StarRailAssistant.utils.Logger import logger


class SRAOperator:
    cloud: bool = False
    web_driver: WebDriver = None
    location_proportion = 1.0
    screenshot_proportion = 1.0
    area_top=0
    area_left=0

    @classmethod
    def _screenshot_region_calculate(cls, region: tuple[int, int, int, int]):
        left, top, width, height = region
        area_width = width // 160 * 160
        area_height = height // 90 * 90
        cls.area_top = top + 45
        cls.area_left = left + 11
        return cls.area_left, cls.area_top, area_width, area_height

    @classmethod
    def _get_screenshot(cls, title: str = ""):
        if cls.cloud:
            bytes_png = cls.web_driver.get_screenshot_as_png()
            image_stream = io.BytesIO(bytes_png)
            pillow_img = Image.open(image_stream)
            return cls._image_resize(pillow_img)
        else:
            matching_windows = pygetwindow.getWindowsWithTitle(title)
            if len(matching_windows) == 0:
                raise WindowNoFoundException('Could not find a window with %s in the title' % title)
            elif len(matching_windows) > 1:
                raise MultipleWindowsException(
                    'Found multiple windows with %s in the title: %s' % (title, [str(win) for win in matching_windows])
                )
            win = matching_windows[0]
            win.activate()
            region = (win.left, win.top, win.width, win.height)
            region = cls._screenshot_region_calculate(region)
            pillow_img = pyscreeze.screenshot(region=region)
            # pillow_img.show()
            return cls._image_resize(pillow_img)

    @classmethod
    def _image_resize(cls, pillow_image: Image):
        if pillow_image.width==1920:
            return pillow_image
        cls.screenshot_proportion = 1920 / pillow_image.width
        resized_image = pillow_image.resize(
            (int(pillow_image.width * cls.screenshot_proportion),
             int(pillow_image.height * cls.screenshot_proportion)),
            Image.BICUBIC)
        # resized_image.show()
        return resized_image

    @classmethod
    def _location_calculator(cls, x, y):
        if cls.cloud:
            html = cls.web_driver.find_element(By.TAG_NAME, "html")
            width = html.size["width"]
            cls.location_proportion = width / 1920
            return x * cls.location_proportion, y * cls.location_proportion
        else:
            cls.location_proportion = 1 / cls.screenshot_proportion
            return x * cls.location_proportion + cls.area_left, y * cls.location_proportion+cls.area_top


    @classmethod
    def _locator(cls, img_path, x_add=0, y_add=0, wait_time=2.0, title="崩坏：星穹铁道") -> tuple[int, int]:
        try:
            time.sleep(wait_time)
            img = cv2.imread(img_path)
            if img is None:
                raise FileNotFoundError("无法找到或读取文件 " + img_path)
            if cls.cloud:
                location = pyautogui.locate(img, cls._get_screenshot(), confidence=0.9)
            else:
                location = pyautogui.locate(img, cls._get_screenshot(title), confidence=0.9)
            x, y = pyautogui.center(location)
            x += x_add
            y += y_add
            x, y = cls._location_calculator(x, y)
            return x, y
        except pyscreeze.PyScreezeException:
            raise WindowNoFoundException("未能找到窗口：" + title)
        except pyautogui.ImageNotFoundException:
            raise MatchFailureError(img_path + " 匹配失败")
        except ValueError:
            raise WindowInactiveException("窗口未激活")
        except FileNotFoundError:
            raise

    @classmethod
    def exist(cls, img_path, wait_time=2):
        """Determine if a situation exists.

        Args:
            img_path (str): Img path of the situation.
            wait_time (int): Waiting time before run.
        Returns:
            True if existed, False otherwise.
        """
        time.sleep(wait_time)  # 等待游戏加载
        try:
            img = cv2.imread(img_path)
            if img is None:
                raise FileNotFoundError("无法找到或读取文件 " + img_path + ".png")
            if cls.cloud:
                pyautogui.locate(img, cls._get_screenshot(), confidence=0.9)
            else:
                pyautogui.locate(img, cls._get_screenshot("崩坏：星穹铁道"), confidence=0.9)
            return True
        except pyautogui.ImageNotFoundException:
            logger.exception(img_path + "匹配失败", is_fatal=True)
            return False
        except FileNotFoundError:
            logger.exception("未找到文件", is_fatal=True)
            return False
        except pyscreeze.PyScreezeException:
            logger.exception("未能找到窗口", is_fatal=True)
            return False
        except ValueError:
            logger.exception("窗口未激活", is_fatal=True)
            return False

    @classmethod
    def get_screen_center(cls):
        """Get the center of game window.

        Returns:
            tuple(x, y)
        """
        if cls.cloud:
            window_size = cls.web_driver.get_window_size()
            window_position = cls.web_driver.get_window_size()
            x, y = window_position.values()
            screen_width, screen_height = window_size.values()
            x, y = cls._location_calculator(x + screen_width // 2, y + screen_height // 2)
            return x, y
        else:
            active_window = pygetwindow.getActiveWindow()
            x, y, screen_width, screen_height = (
                active_window.left,
                active_window.top,
                active_window.width,
                active_window.height,
            )
            return x + screen_width // 2, y + screen_height // 2

    @classmethod
    def click_img(
            cls,
            img_path,
            x_add=0,
            y_add=0,
            wait_time=2.0,
            title="崩坏：星穹铁道"):
        """Click the corresponding image on the screen

        Args:
            img_path (str): Img path.
            x_add (int): X-axis offset(px).
            y_add (int): Y-axis offset(px).
            wait_time (float): Waiting time before run(s).
            title (str): Window title.
        Returns:
            True if clicked successfully, False otherwise.
        """
        try:
            x, y = cls._locator(img_path, x_add, y_add, wait_time, title)
            if cls.cloud:
                action = ActionBuilder(cls.web_driver)
                action.pointer_action.move_to_location(x, y).click()
                action.perform()
            else:
                pyautogui.click(x, y)
            return True
        except Exception:
            logger.exception("点击对象时出错", is_fatal=True)
            return False

    @classmethod
    def click_point(cls, x: int = None, y: int = None) -> bool:
        try:
            if cls.cloud:
                x, y = cls._location_calculator(x, y)
                action = ActionBuilder(cls.web_driver)
                action.pointer_action.move_to_location(x, y).click()
                action.perform()
            else:
                pyautogui.click(x, y)
            return True
        except Exception:
            logger.exception("点击坐标时出错", is_fatal=True)
            return False

    @classmethod
    def press_key(cls, key: str, presses: int = 1, interval: float = 2) -> bool:
        """按下按键

        Args:
            key: 按键
            presses: 按下次数
            interval: 按键间隔时间(如果填入,程序会等待interval秒再按下按键)
        Returns:
            按键成功返回True，否则返回False
        """
        try:
            logger.debug("按下按键" + key)
            if cls.cloud:
                key = cls._key_in_utf8(key)
                for i in range(presses):
                    ActionChains(cls.web_driver).send_keys(key).perform()
                    time.sleep(interval)
            else:
                pyautogui.press(key, presses=presses, interval=interval)
            return True
        except Exception:
            logger.exception("按下按键失败", is_fatal=True)
            return False

    @classmethod
    def press_key_for_a_while(cls, key: str, during: float = 0) -> bool:
        try:
            logger.debug("按下按键" + key)
            if cls.cloud:
                key = cls._key_in_utf8(key)
                ActionChains(cls.web_driver).key_down(key).perform()
                time.sleep(during)
                ActionChains(cls.web_driver).key_up(key).perform()
            else:
                pyautogui.keyDown(key)
                time.sleep(during)
                pyautogui.keyUp(key)
            return True
        except Exception:
            logger.exception("按下按键失败", is_fatal=True)
            return False

    @staticmethod
    def _key_in_utf8(key):
        match key:
            case "esc":
                return "\uE00C"
            case "f1":
                return "\uE031"
            case "f2":
                return "\uE032"
            case "f3":
                return "\uE033"
            case "f4":
                return "\uE034"
            case _:
                raise ValueError("意料之外的按键")

    @classmethod
    def write(cls, content: str = "") -> bool:
        try:
            if cls.cloud:
                ActionChains(cls.web_driver).send_keys(content).perform()
            else:
                pyautogui.write(content)
            return True
        except Exception:
            logger.exception("输入时发生错误", is_fatal=True)
            return False

    @classmethod
    def moveRel(cls, x_offset: int, y_offset: int) -> bool:
        try:
            if cls.cloud:
                x_offset, y_offset = cls._location_calculator(x_offset, y_offset)
                ActionChains(cls.web_driver).move_by_offset(x_offset, y_offset).perform()
            else:
                pyautogui.moveRel(x_offset, y_offset)
            return True
        except Exception:
            logger.exception("移动光标时出错", is_fatal=True)
            return False

    @classmethod
    def find_level(cls, level: str) -> bool:
        """Fine battle level

        Returns:
            True if found.
        """
        x, y = cls.get_screen_center()
        if cls.cloud:
            x,y=cls._location_calculator(x, y)
            action = ActionBuilder(cls.web_driver)
            action.pointer_action.move_to_location(x - 200 * cls.location_proportion, y)
            action.perform()
        else:
            pyautogui.moveTo(x - 200, y)
        while True:
            if cls.exist(level, wait_time=1):
                return True
            else:
                cls.scroll(-1)

    @classmethod
    def scroll(cls, distance: int) -> bool:
        try:
            if cls.cloud:
                ActionChains(cls.web_driver).scroll_by_amount(0, -distance)
            else:
                pyautogui.scroll(distance)
            return True
        except Exception:
            logger.exception("指针滚动时发生错误", is_fatal=True)
            return False

    @classmethod
    def wait_battle_end(cls) -> bool:
        """Wait battle end

        Returns:
            True if battle end.
        """
        logger.info("等待战斗结束")
        quit_battle = cv2.imread("res/img/quit_battle.png")
        while True:
            time.sleep(0.2)
            try:
                if cls.cloud:
                    pyautogui.locate(quit_battle, cls._get_screenshot(), confidence=0.9)
                else:
                    pyautogui.locate(quit_battle, cls._get_screenshot("崩坏：星穹铁道"), confidence=0.9)
                logger.info("战斗结束")
                return True
            except pyautogui.ImageNotFoundException:
                continue
            except pyscreeze.PyScreezeException:
                continue
