"""
micrOS multitask OLED UI
    - with page generation
Designed by Marcell Ban aka BxNxM
"""

from async_oledui.uiframes import (Frame, Cursor, AppFrame,
                                   HeaderBarFrames, PageBarFrame, PopUpFrame,
                                   ScreenSaver, debugging)
from async_oledui import peripheries as periph

from utime import ticks_ms, ticks_diff, sleep_ms
from Common import syslog, micro_task, manage_task, exec_cmd
from Types import resolve
from microIO import bind_pin
# Core modules
from Config import cfgget
# Load Modules
from LM_system import ifconfig, hosts


#################################################################################
#                                    PageUI manager                             #
#                                    (Frame manager)                            #
#################################################################################

class PageUI:
    INSTANCE = None
    DISPLAY = None
    HAPTIC = None

    def __init__(self, w=128, h=64, page=0, poweroff=None, oled_type='ssd1306', control=None, haptic=False):
        """
        :param w: screen width
        :param h: screen height
        :param page: start page index
        :param poweroff: power off after given seconds
        :param oled_type: ssd1306 or sh1106
        :param control: trackball / None
        """
        # OLED setup
        if oled_type.strip() in ('ssd1306', 'sh1106'):
            if oled_type.strip() == 'ssd1306':
                import LM_oled as oled
            else:
                import LM_oled_sh1106 as oled
            PageUI.DISPLAY = oled
            oled.load(width=w, height=h, brightness=50)
        else:
            syslog(f"Oled UI unknown oled_type: {oled_type}")
            Exception(f"Oled UI unknown oled_type: {oled_type}")
        # Trackball & Haptic setup
        self._setup(control, haptic)
        self.width = w-1            # 128 -> 0-127: Good for xy calculation, but absolut width+1 needed!
        self.height = h-1           # 64 -> 0-63: Good for xy calculation, but absolut width+1 needed!
        self.page = page
        self.timer = poweroff
        self._last_page_switch = ticks_ms()
        # Store persistent frame objects
        self.cursor = None
        self.header_bar = None
        self.app_frame = None
        self.page_bar = None
        self.popup = None
        self.screen_saver = None
        # Save
        PageUI.INSTANCE = self
        self.DISPLAY.clean()

    def _setup(self, control:str, haptic:bool):
        """
        :param control: trackball / joystick (todo)
        :param haptic: enable haptic feedback
        """
        haptic_tap = periph.setup(control, self._control_clb, haptic)
        if haptic_tap:
            PageUI.HAPTIC = haptic_tap

    def _boot_msg(self):
        start_x = 24
        start_y = 28
        msg = "Loading..."
        for i in range(0, len(msg)):
            self.DISPLAY.text(msg[0:i+1], start_x, start_y)
            self.DISPLAY.show()
            sleep_ms(100)

    def create(self):
        self._boot_msg()
        # Create managed frames
        self.cursor = Cursor(PageUI.DISPLAY, width=2, height=2, x=0, y=self.height)
        self.header_bar = HeaderBarFrames(PageUI.DISPLAY, timer=self.timer, cursor_draw=self.cursor.draw)
        self.app_frame = AppFrame(PageUI.DISPLAY, self.cursor.draw, width=self.width+1,
                                  height=self.height-15, x=0, y=self.height-53, page=self.page)
        self.app_frame.run("page", period_ms=900)
        self.page_bar = PageBarFrame(PageUI, PageUI.DISPLAY, self.cursor.draw, self.app_frame,
                                     width=self.width+1, height=6, x=0, y=self.height-5)
        self.page_bar.draw()
        self.popup = PopUpFrame(PageUI, PageUI.DISPLAY, self.cursor.draw, self.app_frame, width=self.width+1,
                                  height=self.height-15, x=0, y=self.height-53)
        self.screen_saver = ScreenSaver(PageUI.DISPLAY, width=self.width, height=self.height, x=0, y=0)

    def _control_clb(self, params):
        """
        {"X": trackball.posx, "Y": trackball.posy,
            "S": trackball.toggle, "action": trackball.action}
        """
        action = params.get('action', None)
        if action is not None:
            x, y = params['X'], self.height - params['Y']     # invert Y axes
            self.cursor.update(x, y)
            lut = {"right": "next", "left": "prev"}           # Convert trackball output to control command
            self.control(lut.get(action, action))
            self.DISPLAY.show()

    def control(self, action, force=False):
        # Wake on action
        self.wake()
        # Initial actions:
        self.header_bar.reset_timer()
        self.cursor.draw()

        # Enable page lift-right scroll when footer is selected
        if Cursor.TAG == 'footer' or force:
            delta_t = ticks_diff(ticks_ms(), self._last_page_switch)
            if delta_t > 200:       # Check page switch frequency - max 200ms
                self._last_page_switch = ticks_ms()
                if action == "next":
                    self.app_frame.next()
                if action == "prev":
                    self.app_frame.previous()
                self.page_bar.draw()
        if action == "off":
            Frame.pause_all()
            self.screen_saver.run()
            #self.DISPLAY.poweroff()
        if action == "on":
            self.screen_saver.cancel()
            Frame.resume_all()
            self.DISPLAY.poweron()
        if action == "press":
            if self.popup.selected:
                self.popup.cancel()
            self.app_frame.press()

    def wake(self):
        """Wake up UI from hibernation"""
        if Frame.HIBERNATE:
            self.screen_saver.cancel()
            if callable(PageUI.HAPTIC):
                PageUI.HAPTIC()
            Frame.resume_all()
            self.DISPLAY.poweron()

    @staticmethod
    def add_page(page):
        state = AppFrame.add_page(page)
        pageui = PageUI.INSTANCE
        if state and pageui is not None and pageui.page_bar is not None:
            pageui.page_bar.draw()
        return state

    @staticmethod
    def write_lines(msg, display, x, y, line_limit=3):
        chunk_size = 15
        char_height = 10
        text_x_offset = 3
        # Format message: fitting and \n parsing
        msg = msg.split('\n')
        chunks = [line[i:i + chunk_size] for line in msg for i in range(0, len(line), chunk_size)]
        for i, line in enumerate(chunks):
            if i > line_limit-1:  # max line_limit lines of 13 char
                break
            line_start_y = char_height * i
            display.text(line, x + text_x_offset, y + line_start_y)

    def _press_indicator(self, output, display, w, h, x, y):
        """Dynamic page - draw press callback indicator"""
        if output == "":
            display.text("press", int(x + (w / 2) - 20), y + 30)

    def lm_exec_page(self, page, display, w, h, x, y):
        """
        :param page: LMExecPage with command state
        :param display: display instance
        :param h: frame h
        :param w: frame w
        :param x: frame x
        :param y: frame y
        """
        x, y = x+2, y+4

        def _display_output():
            nonlocal x, y, display
            if page.task_tag is None:
                # Display cached data
                PageUI.write_lines(page.output, display, x, y + 20)
                return
            task_buffer = manage_task(page.task_tag, 'show').replace(' ', '')
            if task_buffer is not None and len(task_buffer) > 0:
                # Update display out to task buffered data
                page.set_output(task_buffer)
                if not manage_task(page.task_tag, 'isbusy'):
                    # data gathered - remove tag - skip re-read
                    page.task_tag = None
            # Display task cached data
            PageUI.write_lines(page.output, display, x, y + 20)

        def _execute(display, w, h, x, y):
            try:
                cmd_list = page.cmd_list()
                if len(cmd_list) == 0:
                    page.set_output("Empty command")
                    return
                # TASK mode: background execution, intercon: >> OR task: &
                if page.background:
                    # BACKGROUND: EXECUTE COMMAND
                    state, out = (exec_cmd(cmd_list, jsonify=True)
                                  if page.task_tag is None else (False, "skip..."))
                    if state:
                        page.task_tag = list(out.keys())[0]
                        buffer = manage_task(page.task_tag, 'show').replace(' ', '')
                        if buffer is not None and len(buffer) > 0:
                            page.set_output(buffer)
                else:
                    # REALTIME mode: get command execution result
                    state, out = exec_cmd(cmd_list, jsonify=True)
                    page.set_output(out)
            except Exception as e:
                page.set_output(e)
            # Print and cache output to display
            PageUI.write_lines(page.output, display, x, y+20)

        # Write command header line and buffered output
        PageUI.write_lines(page.cmd, display, x, y, line_limit=2)
        _display_output()
        # RUN command
        if page.run:
            # Automatic Execution Mode (in page refresh time)
            _execute(display, w, h, x, y)
            return None
        # Button Press Execution Mode (callback)
        self._press_indicator(page.output, display, w, h, x, y)
        # Return "press" callback, mandatory input parameters: display, w, h, x, y
        return {"press": _execute}


class LMExecPage:
    """
    Command page state container.

    One instance is created per genpage call so background task/output state
    cannot bleed across pages while the user navigates.
    """

    def __init__(self, pageui, cmd, run):
        self.pageui = pageui
        self.cmd = cmd
        self.run = run
        self.task_tag = None
        self.output = ""
        self._cmd_list = tuple(cmd.strip().split())
        self.background = (len(self._cmd_list) > 0
                           and ('>>' in self._cmd_list[-1] or '&' in self._cmd_list[-1]))

    def __call__(self, display, w, h, x, y):
        return self.pageui.lm_exec_page(self, display, w, h, x, y)

    def cmd_list(self):
        return list(self._cmd_list)

    def set_output(self, output):
        self.output = str(output)
        if self.pageui.app_frame is not None:
            self.pageui.app_frame.press_output = self.output

    def cancel_task(self):
        if self.task_tag is None:
            return True
        task_tag = self.task_tag
        self.task_tag = None
        try:
            result = manage_task(task_tag, 'kill')
            return result[0] if isinstance(result, tuple) else result
        except Exception as e:
            syslog(f'[ERR] oledui task cancel {task_tag}: {e}')
            return False

    def on_deactivate(self):
        self.cancel_task()
        self.set_output("")


#################################################################################
#                                     Page function                             #
#################################################################################

def _system_page(display, w, h, x, y):
    """
    System basic information page
    """
    devip = ifconfig()[1][0]
    display.text(cfgget("devfid"), x, y+5)
    display.text(f"  {devip}", x, y+15)
    display.text(f"  V: {cfgget('version')}", x, y+25)
    return True

def _intercon_nodes_page(display, w, h, x, y):
    line_limit = 3
    line_start = y+5
    line_cnt = 1
    display.text("InterCon cache", x, line_start)
    cache = hosts()["intercon"]
    if sum([1 for _ in cache]) > 0:
        for key, val in cache.items():
            if '.' in key:
                # IP splitting
                key = key.split('.')[0]
                val = '.'.join(val.split('.')[-2:])
            else:
                # MAC splitting
                key = key.split(':')[0]
                val = ':'.join(val.split(':')[-2:])
            display.text(f" {val} {key}", x, line_start + (line_cnt * 10))
            line_cnt += 1
            if line_cnt > line_limit:
                break
        return True
    display.text("Empty", x+40, line_start + 20)
    return True


def _empty_page(display, w, h, x, y):
    pass

#################################################################################
#                                  Public functions                             #
#################################################################################

def load(width=128, height=64, oled_type="sh1106", control='trackball', poweroff=None,
         haptic=False, i2c_sda=None, i2c_scl=None, trackball_int=None, haptic_pin=None):
    """
    Create async oled UI
    :param width: screen width in pixels
    :param height: screen height in pixels
    :param oled_type: sh1106 / ssd1306
    :param control: trackball / None
    :param poweroff: power off after given seconds
    :param haptic: enable (True) / disable (False) haptic feedbacks (vibration)
    # Optional
    :param i2c_sda: optional OLED/trackball I2C data GPIO number
    :param i2c_scl: optional OLED/trackball I2C clock GPIO number
    :param trackball_int: optional trackball interrupt GPIO number
    :param haptic_pin: optional haptic motor GPIO number
    """
    if PageUI.INSTANCE is None:
        for tag, pin in (('i2c_sda', i2c_sda), ('i2c_scl', i2c_scl),
                         ('trackball_int', trackball_int), ('haptic', haptic_pin)):
            if pin is not None:
                bind_pin(tag, pin)
        ui = PageUI(width, height, poweroff=poweroff, oled_type=oled_type,
                    control=control, haptic=haptic)
        # Add default pages...
        ui.add_page([_system_page, _intercon_nodes_page, _empty_page])
        ui.create()         # Header(4), AppPage(1), PagerIndicator
        return "PageUI was created"
    return "PageUI was already created"


def control(cmd="next"):
    if cmd in ("next", "prev", "on", "off", "press"):
        PageUI.INSTANCE.control(cmd, force=True)
        return cmd
    return f"Unknown action: {cmd}"


def popup(msg='micrOS msg'):
    """
    POP-UP message function
    :param msg: message string
    """
    PageUI.INSTANCE.wake()
    return PageUI.INSTANCE.popup.textbox(msg)


def cancel_popup():
    return PageUI.INSTANCE.popup.cancel()


def cursor(x, y):
    """
    Virtual cursor
    :param x: x coordinate
    :param y: y coordinate
    """
    PageUI.INSTANCE.cursor.update(x, y)
    return "Set cursor position"


def genpage(cmd=None, run=False):
    """
    Create load module execution pages dynamically :)
    - based on cmd value: load_module function (args)
    :param cmd: 'load_module function (args)' string
    :param run: run button event at page init: True/False
    :return: page creation verdict
    """
    if not isinstance(cmd, str):
        return False

    try:
        # Create page for intercon command
        PageUI.INSTANCE.add_page(LMExecPage(PageUI.INSTANCE, cmd, run))
    except Exception as e:
        syslog(f'[ERR] genpage: {e}')
        return str(e)
    return True


def add_page(page_callback):
    """
    [LM] Create page from load module with callback function
    :param page_callback: callback func(display, w, h, x, y)
    """
    if PageUI.INSTANCE is not None:
        return PageUI.INSTANCE.add_page(page_callback)
    return AppFrame.add_page(page_callback)


def debug(state=None):
   return debugging(state)


def help(widgets=False):
    """
    New generation of oled_ui
    - with async frames
    """
    return resolve(
        ("load width=128 height=64 oled_type='sh1106/ssd1306' control='trackball' poweroff=None/sec haptic=False i2c_sda=None i2c_scl=None trackball_int=None haptic_pin=None",
                  "BUTTON control cmd=<prev,press,next,on,off>",
                  "BUTTON debug state=<True,False>", "cursor x y",
                  "popup msg='text'", "cancel_popup",
                  "genpage cmd='system clock'"),
        widgets=widgets)
