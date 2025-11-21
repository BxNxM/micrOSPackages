
from utime import localtime
from Common import syslog, micro_task, manage_task
# Core modules
from Time import uptime
# Load Modules
from LM_system import top, memory_usage, ifconfig, rssi as sta_rssi, list_stations, hosts
try:
    from LM_esp32 import temp as cpu_temp
except Exception as e:
    cpu_temp = None             # Optional function handling
try:
    from LM_gameOfLife import next_gen as gol_nextgen, reset as gol_reset
except:
    gol_nextgen = None          # Optional function handling

DEBUG = False

def debugging(state:bool=None):
    global DEBUG
    if state is None:
        return DEBUG
    DEBUG = state
    return DEBUG

#################################
#          Frame classes        #
#################################

class BaseFrame:

    def __init__(self, display, width, height, x=0, y=0):
        """Basic pixel frame properties"""
        self.display = display      # Display object
        self.w = width              # Frame width
        self.h = height             # Frame height
        self.x = x                  # Frame start X
        self.y = y                  # Frame start Y
        self.selected = False       # Store frame instance selection - updated by Cursor
        self.paused = False         # Async task pause feature (Frame class)

    def clean(self):
        """Clean pixel frame area"""
        self.display.rect(x=self.x, y=self.y, w=self.w, h=self.h, state=0, fill=True)
        if self.selected or DEBUG:
            self.display.rect(x=self.x, y=self.y, w=self.w, h=self.h, state=1, fill=False)

    def select(self, x, y):
        """Select frame based on x,x aka cursor"""
        if self.x <= x <= self.x + self.w+1 and self.y <= y <= self.y + self.h:
            if not self.selected:
                self.selected = True
                self.display.rect(x=self.x, y=self.y, w=self.w, h=self.h, state=1, fill=False)
        else:
            self.selected = False
        return self.selected

    def pause(self, state=None):
        """Used by child classes to control internal execution loop state"""
        if state is None:
            return self.paused
        self.paused = state
        return self.paused


class Frame(BaseFrame):
    # Collect all created Frame objects
    FRAMES = set()
    HIBERNATE = False

    def __init__(self, display, callback, width, height, x=0, y=0, tag="", hover_clb=None, press_clb=None):
        super().__init__(display, width, height, x, y)
        # Store callbacks
        self.callback = callback        # Main callback - draw or run
        self.hover_clb = hover_clb      # Hover callback - optional
        self.press_clb = press_clb      # Press callback - optional
        self.tag = tag                  # used for frame identification
        self._taskid = None             # used for task identification
        self._fast_refresh = False       # Interrupt app frame task sleep - for callback reload
        Frame.FRAMES.add(self)          # Store - managed frames

    def draw(self):
        """
        Redraw frame
        """
        self.clean()
        # Pass adjusted useful area
        try:
            self.callback(self.display, self.w - 2, self.h - 2, self.x + 1, self.y + 1)
        except Exception as e:
            syslog(f"[ERR] Frame clb: {e}")
        self.display.show()
        return f"Draw {self._taskid} frame"

    async def _task(self, period_ms):
        """
        Frame task - draw executor
        """
        with micro_task(tag=self._taskid) as my_task:
            s = None
            micro_sleep_ms = 50
            period_ms = micro_sleep_ms if period_ms < micro_sleep_ms else period_ms
            while True:
                if s != self.paused:
                    my_task.out = 'paused' if self.paused else f'refresh: {period_ms} ms'
                    s = self.paused
                if self.paused:
                    await my_task.feed(sleep_ms=period_ms) # extra wait in paused mode
                else:
                    # Draw/Refresh frame
                    self.draw()
                # Async sleep - feed event loop
                for micro_sleep in range(0, period_ms, micro_sleep_ms):
                    if self._fast_refresh:
                        self._fast_refresh = False
                        break
                    await my_task.feed(sleep_ms=micro_sleep_ms)

    def clb_refresh(self):
        """Fast reload app loop callbacks"""
        self._fast_refresh = True

    def run(self, tid, period_ms=500):
        """
        Start registered callback frame task
        """
        # [!] ASYNC TASK CREATION [1*] with async task callback + taskID (TAG) handling
        self._taskid = f"oledui.{tid}"
        return micro_task(tag=self._taskid, task=self._task(period_ms=period_ms))

    def hover(self):
        """
        Called by Cursor
        """
        if PopUpFrame.INSTANCE is None:
            return False
        if callable(self.hover_clb):
            PopUpFrame.INSTANCE.run(self.hover_clb)
            return True
        return False

    def press(self):
        """
        Redraw frame on press
            - PageUI control
        """
        if self.press_clb is None:
            return
        self.clean()
        # Pass adjusted useful area
        try:
            self.press_clb(self.display, self.w - 2, self.h - 2, self.x + 1, self.y + 1)
        except Exception as e:
            syslog(f"[ERR] Frame press clb: {e}")
        self.display.show()

    @staticmethod
    def pause_all():
        """
        Pause all managed frames
        """
        Frame.HIBERNATE = True
        for frame in Frame.FRAMES:
            frame.pause(True)

    @staticmethod
    def resume_all():
        """
        Resume all managed frames
        """
        Frame.HIBERNATE = False
        for frame in Frame.FRAMES:
            frame.pause(False)
            frame.draw()

    @staticmethod
    def get_frame(tag):
        """
        Get frame by tag
        """
        for frame in Frame.FRAMES:
            if frame.tag == tag:
                return frame


class Cursor(BaseFrame):
    TAG = ""                # Selected/Active frame tag

    def __init__(self, display, width, height, x=0, y=0):
        super().__init__(display, width, height, x, y)
        self.pos_xy = (x, y)

    def draw(self):
        x, y = self.pos_xy
        new_x = x if x-1 < 0 else x-1
        new_y = y+1
        self.display.rect(new_x, new_y, 2, 2, 1)  # draw new cursor
        self.display.show()

    def update(self, x, y):
        """
        Update cursor with
        - cursor position
        - frame selection
        """
        self.clean()
        self.pos_xy = (x, y)
        for frame in Frame.FRAMES:
            if frame.select(x, y):          # select/deselect frame based on coordinates
                # Frame was found
                if frame.tag != Cursor.TAG:
                    # Change event
                    if Cursor.TAG == "footer" and PageBarFrame.INSTANCE:
                        # Leave footer event - clean selection
                        PageBarFrame.INSTANCE.selected = False
                        PageBarFrame.INSTANCE.draw()
                    # Update TAG
                    Cursor.TAG = frame.tag
                    # Handle hover action
                    has_hover = frame.hover()
                    if not has_hover:
                        PopUpFrame.INSTANCE.cancel()
        self.draw()

    def clean(self):
        """
        Clean previous cursor
        """
        x, y = self.pos_xy
        self.display.rect(x - 1, y + 1, 2, 2, 0)


class PopUpFrame(BaseFrame):
    INSTANCE = None

    def __init__(self, pageui, display, cursor_draw, app_frame, width, height=5, x=0, y=0):
        super().__init__(display, width, height, x=x, y=y)
        self.cursor_draw = cursor_draw
        self.app_frame = app_frame
        self.callback = None
        self.pageui = pageui
        self._taskid = None
        offset = 6
        self._inner_x = self.x + offset
        self._inner_y = self.y + offset
        self._inner_w = self.w - (offset * 2)
        self._inner_h = self.h - (offset * 2)
        PopUpFrame.INSTANCE = self

    def _draw_icon(self):
        # Frame
        if DEBUG:
            self.display.rect(self._inner_x, self._inner_y, self._inner_w, self._inner_h)
        # Info sign
        x = self._inner_x+2
        y_dot = self._inner_y+4
        y_base = y_dot+8
        width = 6
        self.display.rect(x, y_dot, width, 6, fill=1)         # .
        self.display.rect(x, y_base, width, 14, fill=1)       # i

    def draw(self):
        """Draw callback"""
        self.clean()
        self._draw_icon()
        if callable(self.callback):
            text_x_offset = 15
            self.callback(self.display, self._inner_w, self._inner_h, self._inner_x+text_x_offset, self._inner_y+4)
        self.display.show()
        self.cursor_draw()
        return f"Draw {self._taskid} frame"

    def run(self, callback):
        """Start draw task with callback"""
        # [!] ASYNC TASK CREATION [1*] with async task callback + taskID (TAG) handling
        self.app_frame.pause(True)
        self.selected = True
        self.callback = callback
        self.draw()

    def textbox(self, msg):
        """
        Draw PopUp Textbox
        """
        # Prepare
        self.app_frame.pause(True)
        self.selected = True
        self.clean()
        self._draw_icon()
        # Format message: fitting and \n parsing
        text_x_offset = 12
        self.pageui.write_lines(msg, self.display, self._inner_x + text_x_offset, self._inner_y+4, line_limit=3)
        self.display.show()
        return f"Draw textbox frame"

    def cancel(self):
        if self.selected:
            self.selected = False
            self.clean()
            self.app_frame.pause(False)
            if self._taskid is not None:
                self._taskid = None
                return manage_task(self._taskid, "kill")
        return True


class PageBarFrame(Frame):
    INSTANCE = None

    def __init__(self, pageui, display, cursor_draw, app_frame, width, height=5, x=0, y=0, tag="footer"):
        super().__init__(display, self._page_indicator, width, height, x=x, y=y, tag=tag)
        self.cursor_draw = cursor_draw
        self.app_frame = app_frame
        self.pageui = pageui
        self._trigger_limit_ms = 100
        PageBarFrame.INSTANCE = self

    def _page_indicator(self, display, w, h, x, y):
        if callable(self.pageui.HAPTIC):
            self.pageui.HAPTIC()
        page_cnt = len(AppFrame.PAGES)
        plen = int(round(w / page_cnt))
        # Draw active page indicator
        display.rect(x+self.app_frame.active_page_index*plen+1, y+1, plen-2, h-2, fill=True)
        self.cursor_draw()

class ScreenSaver(BaseFrame):
    INSTANCE = None

    def __init__(self, display, width, height, x=0, y=0):
        super().__init__(display, width+1, height+1, x=x, y=y)
        self.running = False
        ScreenSaver.INSTANCE = self

    def screen_saver(self):
        # Default mode
        if gol_nextgen is None:
            self.cancel()
            self.display.poweroff()
            return      # __power_save / no game of life screen saver
        # Screen saver mode
        matrix = gol_nextgen(raw=True)
        if matrix is None:
            self.cancel()
            self.display.poweroff()
        else:
            # Update display with Conway's Game of Life
            self.clean()
            matrix_height = len(matrix)
            for line_idx, line in enumerate(matrix):
                for x_idx, v in enumerate(line):
                    scale = int(self.h / matrix_height)
                    if scale == 1:
                        self.display.pixel(x_idx, line_idx, color=v)
                    else:
                        self.display.rect(x_idx*scale, line_idx*scale, w=scale, h=scale, state=v, fill=True)
            self.display.show()

    async def _task(self, period_ms):
        self.running = True
        with micro_task(tag="oledui.anim") as my_task:
            counter = 0
            while self.running:
                counter += 1
                self.screen_saver()
                # Store data in task cache (task show mytask)
                my_task.out = f'GameOfLife: {counter}'
                # Async sleep - feed event loop
                await my_task.feed(sleep_ms=period_ms)
            my_task.out = f'GameOfLife stopped: {counter}'

    def run(self, fps=10):
        # [!] ASYNC TASK CREATION [1*] with async task callback + taskID (TAG) handling
        period_ms = int(1000/fps)
        return micro_task(tag="oledui.anim", task=self._task(period_ms))

    def cancel(self):
        if self.running:
            self.running = False
            gol_reset()
            self.clean()


class AppFrame(Frame):
    PAGES = []

    def __init__(self,  display, cursor_draw, width, height, x=0, y=0, tag="app", page=0):
        super().__init__(display, self._application, width, height, x=x, y=y, tag=tag)
        self.active_page_index = page
        self.cursor_draw = cursor_draw
        self.press_output = ""

    def _application(self, display, width, height, x=0, y=0):
        if len(AppFrame.PAGES) > 0:
            page = AppFrame.PAGES[self.active_page_index]
            # Pass adjusted useful area
            try:
                output = page(display, width, height, x, y)
                # Add user press callback from page output
                self.press_clb = output.get("press", None) if isinstance(output, dict) else None
            except Exception as e:
                display.text(e, x, y)
        self.cursor_draw()

    @staticmethod
    def add_page(page):
        if callable(page):
            AppFrame.PAGES.append(page)     # add single page
            return True
        if isinstance(page, list):
            AppFrame.PAGES += page          # add list of pages
            return True
        return False

    def next(self):
        pages_cnt = len(AppFrame.PAGES) - 1
        self.active_page_index += 1
        if self.active_page_index > pages_cnt:
            self.active_page_index = 0
        self.clb_refresh()
        self.press_output = ""

    def previous(self):
        pages_cnt = len(AppFrame.PAGES) - 1
        self.active_page_index -= 1
        if self.active_page_index < 0:
            self.active_page_index = pages_cnt
        self.clb_refresh()
        self.press_output = ""


class HeaderBarFrames:

    def __init__(self, display, cursor_draw, timer=30):
        self.display = display
        self.cursor_draw = cursor_draw
        self.timer = [timer, timer]     #[0] default value, [1] timer cnt
        # Create header: time frame
        time_frame = Frame(self.display, self._time, width=66, height=10, x=32, y=0, tag="time",
                           hover_clb=self._time_hover)
        time_frame.run("time", period_ms=1000)
        # Create header: cpu,mem metrics
        cpu_mem_frame = Frame(self.display, self._cpu_mem, width=12, height=10, x=116, y=0, tag="cpu_mem",
                              hover_clb=self._cpu_mem_hover)
        cpu_mem_frame.run('cpu_mem', period_ms=2100)
        # Create header: wifi rssi
        rssi_frame = Frame(self.display, self._rssi, width=10, height=10, x=0, y=0, tag="rssi",
                           hover_clb=self._rssi_hover)
        rssi_frame.run('rssi', period_ms=4200)
        # Create header: timer frame (auto sleep)
        if isinstance(timer, int):
            timer_frame = Frame(self.display, self._timer, width=8, height=10, x=14, y=0, tag="timer",
                                hover_clb=self._timer_hover)
            timer_frame.run("timer", period_ms=int((timer*1000)/24))

    def _time(self, display, w, h, x, y):
        # Built-in: time widget frame
        ltime = localtime()
        try:
            h = f"0{ltime[-5]}" if len(str(ltime[-5])) < 2 else ltime[-5]
            m = f"0{ltime[-4]}" if len(str(ltime[-4])) < 2 else ltime[-4]
            s = f"0{ltime[-3]}" if len(str(ltime[-3])) < 2 else ltime[-3]
        except:
            h, m, s = 0, 0, 0
        display.text(f"{h}:{m}:{s}", x, y)
        self.cursor_draw()

    def _time_hover(self, display, w, h, x, y):
        display.text(f"Uptime:", x, y)
        display.text(uptime(), x+10, y+10)
        self.cursor_draw()

    def _timer(self, display, w=5, h=5, x=0, y=0):
        # Built-in: timer widget frame
        _view = int(w * h * (self.timer[1] / self.timer[0]))
        _complete_lines_cnt = int(_view / w)             # complete lines number
        _sub_line_x = _view - (_complete_lines_cnt * w)  # incomplete line width
        for _l in range(0, h):
            if _l < _complete_lines_cnt:
                display.line(x, y+_l, x+w, y+_l)
            else:
                display.line(x, y+_l, x+_sub_line_x, y+_l)
                break
        self.timer[1] -= 1
        if self.timer[1] <= 0:
            # Pause All Frame tasks
            self.hibernate(display, w, h, x, y)

    def _timer_hover(self, display, w, h, x, y):
        display.text("Power off in", x, y)
        display.text(f"{self.timer[1]} sec", x+10, y+10)
        self.cursor_draw()

    def hibernate(self, display, w, h, x, y):
        Frame.pause_all()
        if ScreenSaver.INSTANCE is None:
            self.display.poweroff()
        else:
            ScreenSaver.INSTANCE.run()
        self.reset_timer()

    def reset_timer(self):
        self.timer[1] = self.timer[0]

    def _cpu_mem(self, display, w, h, x, y):
        # Built-in: cpu_mem widget frame
        sys_usage = top()
        cpu = sys_usage.get('CPU load [%]', 100)
        cpu = 100 if cpu > 100 else cpu  # limit cpu overload in visualization
        mem = sys_usage.get('Mem usage [%]', 100)
        _cpu_limit, _mem_limit = cpu > 90, mem > 70  # fill indicator (limit)
        _cpu, _mem = int(h * (cpu / 100))+1, int(h * (mem / 100))+1
        width = int((w-2)/2)
        y_base = y+h
        spacer = 3
        display.rect(x, y_base-_cpu, w=width, h=_cpu, fill=_cpu_limit)  # cpu usage indicator
        display.rect(x+width+spacer, y_base-_mem, w=width, h=_mem, fill=_mem_limit)  # memory usage indicator
        self.cursor_draw()

    def _cpu_mem_hover(self, display, w, h, x, y):
        sys_usage = top()                                   # Get CPU and MEM usage percentage
        mem_kb = int(memory_usage().get("mem_used", 0) / 1000)     # Get MEM usage in kb
        cpu = sys_usage.get('CPU load [%]', 100)
        mem = sys_usage.get('Mem usage [%]', 100)
        cpu_t = ""
        if callable(cpu_temp):
            _cpu_t = int(list(cpu_temp().values())[0])
            cpu_t = f"{_cpu_t}C" if _cpu_t > 0 else ""
        display.text(f"CPU {cpu}%  {cpu_t}", x, y)
        display.text(f"MEM {mem}%", x, y+10)
        display.text(f"{mem_kb}kb", x+32, y+20)
        self.cursor_draw()

    @staticmethod
    def __rssi_into():
        value = list(sta_rssi().values())[0]
        min_rssi, max_rssi = -90, -40
        rssi = max(min_rssi, min(max_rssi, value))
        rssi_ratio = ((rssi - min_rssi) / (max_rssi - min_rssi))
        return round(rssi_ratio, 1), value

    def _rssi(self, display, w, h, x, y):
        # Built-in: _rssi widget frame
        x = min(x-1, 0)                     # visual offset in start_x
        rssi_ratio, _ = self.__rssi_into()
        # Top level line indicator
        display.line(x, y, x+w, y)
        # Calculate lines
        start_line_y = y+h-1
        end_line_y = y + int(h*(1-rssi_ratio))
        for y_index in range(start_line_y, end_line_y, -1):
            end_x = x + min(w, w-int(w*(y_index/start_line_y))+1)
            display.line(x, y_index, end_x, y_index)
        # Button level line indicator
        display.line(x, y+h-1, x+1, y+h-1)
        self.cursor_draw()

    def _rssi_hover(self, display, w, h, x, y):
        nw_mode = ifconfig()[0]
        if nw_mode == "STA":
            rssi_ratio, strength = self.__rssi_into()
            display.text(f"{nw_mode} mode", x, y)
            display.text(f"rssi: {rssi_ratio*100}%", x+10, y+10)
            display.text(f"{strength}dBm", x+50, y + 20)
        elif nw_mode == "AP":
            display.text(f"{nw_mode} mode", x, y)
            devs_mac = [d[0] for d in list_stations()]
            for i, mac in enumerate(devs_mac):
                display.text(f"{mac}", x, y + 9 + (i*9))
                if i > 2:
                    break
        else:
            display.text(f"{nw_mode} mode", x, y)
        self.cursor_draw()
