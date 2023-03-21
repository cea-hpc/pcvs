import os
import pprint
from pathlib import Path
from typing import Iterable

from textual import on
from textual.app import App
from textual.containers import Container, Grid, Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import (Button, DataTable, DirectoryTree, Footer, Header,
                             Input, LoadingIndicator, OptionList, Static,
                             TextLog)
from textual.widgets.option_list import Option

from pcvs.helpers.utils import check_is_build_or_archive
from pcvs.ui.textual.report.model import ReportModel


class ActiveSessionList(Widget):
    items = reactive(OptionList())
    selected = None
    
    def compose(self):
        self.init_list()
        yield Static("Loaded Sessions:")
        yield self.items
        yield Horizontal(
                Button(label="Done", variant="primary", id="session-pick-done"),
                Button(label="Cancel", variant="error", id="session-pick-cancel")
            )
    
    def init_list(self):
        item_names = self.app.model.session_prefixes
        active = self.app.model.active.prefix
        assert(active in item_names)
        
        self.item_list = list()
        for name in item_names:
            self.item_list.append(Option(name))
        
        self.app.query_one(ActiveSessionList).items = OptionList(*self.item_list)
    
    @on(OptionList.OptionSelected)
    def select_line(self, event):
        self.selected = event.option.prompt
        
    def add(self, path):
        if path not in self.item_list:
            self.item_list.append(path)
            self.app.query_one(ActiveSessionList).items.add_option(item=path)


class FileBrowser(Widget):
    BINDINGS = [('q', 'pop_screen', 'Back')]
    last_select = None
    log = reactive(Static(id="error-log"))
    
    class CustomDirectoryTree(DirectoryTree):
        def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
            return [path for path in paths if check_is_build_or_archive(path) or os.path.isdir(path)]
    
    def compose(self):
        yield Static("File Browser:")
        yield self.CustomDirectoryTree(os.getcwd(), id="filepicker")
        yield Static("Direct path:")
        yield Input(placeholder="Valid PCVS prefix")
        yield Button(label="Add", variant="primary", id="add-session")
        yield self.log
    
    @on(DirectoryTree.FileSelected) 
    def on_seleted_line(self, event: DirectoryTree.FileSelected):
        event.stop()
        FileBrowser.last_select = event.path


class SessionPickScreen(ModalScreen):
    def compose(self):
        yield Grid(
            ActiveSessionList(),
            FileBrowser(),
            id="session-list-screen"
        )
    
    class SwitchAnotherSession(Message):
        pass

    @on(Button.Pressed, "#session-pick-cancel")
    def pop_screen(self, event):
        self.app.pop_screen()
    
    @on(Button.Pressed, "#session-pick-done")
    def set_active_session(self, event):
        selected_row = self.query_one(ActiveSessionList).selected
        self.app.model.set_active(selected_row)
        self.post_message(SessionPickScreen.SwitchAnotherSession())
        self.app.pop_screen()
    
    @on(Button.Pressed, "#add-session")
    def add_from_file_browser(self, event):
        if self.query_one(Input).value:
            path = os.path.abspath(os.path.expanduser(self.query_one(Input).value))
        else:
            path = FileBrowser.last_select
        if path is None:
            return
        path = str(path)
        if not check_is_build_or_archive(path):
            self.query_one(FileBrowser).log.update("{} is not a valid PCVS prefix".format(path))
            return
        else:
            self.query_one(FileBrowser).log.update("")

        sid = self.app.model.add_session(path)
        self.app.model.set_active(sid)
        self.app.query_one(ActiveSessionList).add(path)


class JobListViewer(Widget):
    name_colkey = None
    jobgroup = {}
    table = reactive(DataTable())
    
    def compose(self):
        self.table.focus()
        self.table.zebra_stripes = True
        self.table.cursor_type = "row"
        self.name_colkey, _, _ = self.table.add_columns("Name", "Status", "Time (s)")
        self.update_table()
        
        yield Grid(self.table)

    def update_table(self):
        self.table.clear()
        for state, jobs in self.app.model.single_session_status(self.app.model.active_id).items():
            for jobid in jobs:
                obj = self.app.model.single_session_map_id(self.app.model.active_id, jobid)
                
                color = self.app.model.pick_color_on_status(obj.state)
                
                self.table.add_row(
                    obj.name,
                    "[{c}]{i}[/{c}]".format(c=color, i=obj.state),
                    obj.time
                )
                self.jobgroup[obj.name] = obj
        self.table.sort(self.name_colkey)
    
class SingleJobViewer(Widget):
    log = reactive(TextLog(wrap=True))
    cmd = reactive(Static())
    
    def compose(self):
        yield self.cmd
        yield self.log
        
    def watch_log(self, old, new):
        self.log = new
    
    def watch_cmd(self, old, new):
        self.cmd = new

class MainScreen(Screen):
    def compose(self):
        #with TabbedContent():
        #    with TabPane("main", id="main"):
            #with TabPane("main2", id="main2"):
        yield Header()
        yield JobListViewer()
        yield SingleJobViewer()
        yield Footer()
        
    @on(DataTable.RowSelected)
    def selected_row(self, event: DataTable.RowSelected):
        name_colkey = self.query_one(JobListViewer).name_colkey
        jobname = self.query_one(DataTable).get_cell(event.row_key, name_colkey)
        
        obj = self.query_one(JobListViewer).jobgroup[jobname]
        data = "** No Output **" if not obj.output else obj.output
        
        self.query_one(SingleJobViewer).cmd.update(obj.command)
        logger = self.query_one(SingleJobViewer).log
        logger.clear()
        logger.write(data)
        

class ExitConfirmScreen(ModalScreen):
    def compose(self):
        yield Grid(
                Static("Are you sure you want to quit?", id="question"),
                Button("Quit", variant="error", id="quit"),
                Button("Cancel", variant="primary", id="cancel"),
                id="dialog",
                )

    @on(Button.Pressed)
    def press_exit_screen_button(self, event):
        if event.button.id == "quit":
            self.app.exit()
        else:
            self.app.pop_screen()
        
class PleaseWaitScreen(ModalScreen):
    def compose(self):
        yield Static("Please Wait...")
        yield LoadingIndicator()
    

class SessionInfoScreen(ModalScreen):
    def compose(self):
        display = {
            "datetime": Static("Date of run:"),
            "pf_name": Static("Profile:"),
        }
        config = self.app.model.active.config
        infolog = TextLog()
        
        infolog.write(pprint.pformat(config))

        yield Container(
            Horizontal(
                Static('File Path:'),
                Static(self.app.model.active.prefix),
            ),
            Static('Configuration:'),
            infolog,
            Button("Done"),
            id="session-infos"
        )
    
    @on(Button.Pressed)
    def quit_infos(self, ev):
        self.app.pop_screen()

class ReportApplication(App):
    TITLE = "PCVS Job Result Viewer"
    SCREENS = {
        "main": MainScreen(),
        "exit": ExitConfirmScreen(),
        "wait": PleaseWaitScreen(),
        "session_list": SessionPickScreen(),
        "session_infos": SessionInfoScreen()
        }
    BINDINGS = {
        ('q', 'push_screen("exit")', 'Exit'),
        ('o', 'push_screen("session_list")', 'Open'),
        ('t', 'toggle_dark', 'Dark mode'),
        ("c", "push_screen('session_infos')", 'Infos')
    
    }
    CSS_PATH = "main.css"
    
    @on(SessionPickScreen.SwitchAnotherSession)
    def switch_session(self, event):
        #self.app.push_screen("wait")
        self.app.query_one(JobListViewer).update_table()
        #self.app.pop_screen()
        
        
    def on_mount(self):
        self.push_screen('main')
        
    def __init__(self, model):
        self.model: ReportModel = model
        super().__init__()
    
def start_app(p=None) -> int:
    app = ReportApplication(ReportModel(p)).run()