import os
from sqlite3 import Row

import npyscreen
from genericpath import isfile

from pcvs import NAME_BUILDIR
from pcvs import dsl
from pcvs.backend import bank as pvBank


class Controller:
    def __init__(self, path, serie=None):
        self.bank = dsl.Bank(path, serie)


class DirForm(npyscreen.ActionPopup):

    def update_dir(self):
        new_path = self._filepath.value
        l = []
        for comb in ['.', NAME_BUILDIR]:
            path = os.path.join(new_path, comb)
            if not os.path.isdir(path):
                continue
            for file in os.listdir(path):
                if os.path.isfile(os.path.join(path, file)) and file.startswith("pcvsrun_") and file.endswith(".tar.gz"):
                    l.append(file)

        self._box.values = l
        self.display()

    def on_ok(self):
        self.parentApp.getForm("MAIN").focus = (
            "archive", self._box.get_selected_objects())
        self.parentApp.switchFormPrevious()

    def on_cancel(self):
        self.parentApp.switchFormPrevious()

    def create(self):
        self._filepath = self.add(
            npyscreen.TitleFilename, name="Search Path:", value=os.getcwd())
        self.add(npyscreen.MiniButtonPress, name="Search",
                 when_pressed_function=self.update_dir)
        self._box = self.add(npyscreen.TitleSelectOne,
                             name="Available archives:")

        # self.update_dir()


class BankForm(npyscreen.Popup):
    def create(self):

        pvBank.init()

        t = self.add(npyscreen.SelectOne, name="Available series:")
        t.values = []
        for b in pvBank.BANKS:
            bank = pvBank.Bank(token=b)
            for series in bank.list_all().values():
                for serie in series:
                    t.values.append("{}@{}".format(bank.name, serie.name))


class LabelSelect(npyscreen.MultiLineAction):
    def __init__(self, *args, **keywords):
        super().__init__(*args, **keywords)

    def actionHighlighted(self, act_on_this, keypress):
        self.parent.parentApp.getForm('MAIN').subtrees.values = [1, 2, 3, 4]


class LabelBox(npyscreen.BoxTitle):
    _contained_widget = LabelSelect


class TreeView(npyscreen.FormWithMenus):
    focus = None

    def create(self):
        self.labels = self.add(LabelBox, name="Labels",
                               max_width=20, max_height=10, relx=2, rely=2)
        self.subtrees = self.add(
            npyscreen.BoxTitle, name="Subtree(s)", rely=12, max_width=20, max_height=20)
        self.tests = self.add(npyscreen.BoxTitle,
                              name="Test(s)", relx=22, rely=2, max_height=30)
        self.results = self.add(npyscreen.BoxTitle, name="Result(s)")

        menu = self.add_menu(name="Menu", shortcut="^X")
        menu_load = menu.addNewSubmenu(name="Load from", shortcut="^L")
        menu_load.addItemsFromList([
            ("Directory", self.load_directory),
            ("Bank Name", self.load_bank)
        ])
        menu.addItemsFromList([
            ("Exit", self.exit_application)
        ])

    def beforeEditing(self):
        if self.focus:
            self.labels.values = [1, 2, 3, 4]
            self.labels.display()

    def afterEditing(self):
        pass
        #npyscreen.notify_wait("Loading Results in {}".format("TBD"), "PROGRESS", wide=True)

    def load_directory(self):
        self.parentApp.setNextForm('DIRSEL')
        self.parentApp.switchFormNow()

    def load_bank(self):
        self.parentApp.setNextForm('BANKSEL')
        self.parentApp.switchFormNow()

    def exit_application(self):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()


class Application(npyscreen.NPSAppManaged):
    ctl = None

    def onStart(self):
        npyscreen.setTheme(npyscreen.Themes.ColorfulTheme)
        self.__form = TreeView(name="Reporting Interface")
        self.registerForm("MAIN", self.__form)
        self.registerForm("DIRSEL", DirForm(name="Directory Selection"))
        self.registerForm("BANKSEL", BankForm(name="Bank Selection"))


if __name__ == "__main__":
    try:
        a = Application()
        a.ctl = Controller("demo", "project/baf9469ef60995d5405af590ba68d489")
        a.run()
    except KeyboardInterrupt:
        pass
