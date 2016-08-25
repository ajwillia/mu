"""
Copyright (c) 2015-2016 Nicholas H.Tollervey and others (see the AUTHORS file).

Based upon work done for Puppy IDE by Dan Pope, Nicholas Tollervey and Damien
George.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import keyword
import os
import re
import logging
from PyQt5.QtCore import QSize, Qt, pyqtSignal, QIODevice
from PyQt5.QtWidgets import (QToolBar, QAction, QStackedWidget, QDesktopWidget,
                             QWidget, QVBoxLayout, QShortcut, QSplitter,
                             QTabWidget, QFileDialog, QMessageBox, QTextEdit,
                             QFrame, QListWidget, QGridLayout, QLabel, QMenu,
                             QListWidgetItem)
from PyQt5.QtGui import QKeySequence, QColor, QTextCursor, QFontDatabase
from PyQt5.Qsci import QsciScintilla, QsciLexerPython, QsciAPIs
from PyQt5.QtSerialPort import QSerialPort
from mu.contrib import microfs
from mu.resources import load_icon, load_stylesheet, load_font_data


#: The default font size.
DEFAULT_FONT_SIZE = 14
#: All editor windows use the same font
FONT_NAME = "Source Code Pro"
FONT_FILENAME_PATTERN = "SourceCodePro-{variant}.otf"
FONT_VARIANTS = ("Bold", "BoldIt", "It", "Regular", "Semibold", "SemiboldIt")

# Load the two themes from resources/css/[night|day].css
#: NIGHT_STYLE is a dark high contrast theme.
NIGHT_STYLE = load_stylesheet('night.css')
#: DAY_STYLE is a light conventional theme.
DAY_STYLE = load_stylesheet('day.css')


logger = logging.getLogger(__name__)

def umakedirs(name, serial):
    """
    umakedirs(name, serial)

    Super-mkdir for the microfs.  Modified from os.makedirs; 
    
    create a leaf directory and all intermediate ones.  Works like
    mkdir, except that any intermediate path segment (not just the rightmost)
    will be created if it does not exist. 

    This is recursive.

    """
    head, tail = os.path.split(name)
    if not tail:
        head, tail = os.path.split(head)
    if head and tail and not microfs.path_exists(head, serial):
        try:
            umakedirs(head, serial)
        except FileExistsError:
            # be happy if someone already created the path
            pass
        cdir = microfs.getcwd(serial)
        if isinstance(tail, bytes):
            cdir = bytes(curdir, 'ASCII')
        if tail == cdir:           # xxx/newdir/. exists if xxx/newdir exists
            return
    try:
        microfs.mkdir(name, serial)
    except OSError as e:
        # ignore the exception of the directory already existing
        pass


def ucopytree(src, dst, serial):
    """
    Recursively copy a directory tree from the local system (src) to the
    micropython device (dst).
       
    Modified from shutil.copytree
    """
    
    names = os.listdir(src)


    umakedirs(dst, serial)
    errors = []
    for name in names:
        
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.isdir(srcname):
                ucopytree(srcname, dstname, serial)
            else:
                # Will raise a SpecialFileError for unsupported file types
                microfs.put2(srcname, target=dstname, serial=serial)
        # catch the Error from the recursive ucopytree so that we can
        # continue with other files
        except Error as err:
            errors.extend(err.args[0])
        except OSError as why:
            errors.append((srcname, dstname, str(why)))
    
    if errors:
        raise Error(errors)
    return dst

def urmtree(path, serial):
    """
    Recursively delete a directory tree and all contents        
    """

    for item in microfs.ls2(serial, d=path):
        name, item_type = item
        full_path = os.path.join(path, name)
        if item_type == "D":
            full_path = os.path.join(path, name)
            urmtree(full_path, serial)
            #microfs.rm(serial, full_path)
        else:
            microfs.rm(serial, full_path)
    microfs.rm(serial, path)

class Font:
    """
    Utility class that makes it easy to set font related values within the
    editor.
    """
    _DATABASE = None

    def __init__(self, color='black', paper='white', bold=False, italic=False):
        self.color = color
        self.paper = paper
        self.bold = bold
        self.italic = italic

    @classmethod
    def get_database(cls):
        """
        Create a font database and load the MU builtin fonts into it.
        This is a cached classmethod so the font files aren't re-loaded
        every time a font is refereced
        """
        if cls._DATABASE is None:
            cls._DATABASE = QFontDatabase()
            for variant in FONT_VARIANTS:
                filename = FONT_FILENAME_PATTERN.format(variant=variant)
                font_data = load_font_data(filename)
                cls._DATABASE.addApplicationFontFromData(font_data)
        return cls._DATABASE

    def load(self, size=DEFAULT_FONT_SIZE):
        """
        Load the font from the font database, using the correct size and style
        """
        return Font.get_database().font(FONT_NAME, self.stylename, size)

    @property
    def stylename(self):
        """
        Map the bold and italic boolean flags here to a relevant
        font style name.
        """
        if self.bold:
            if self.italic:
                return "Semibold Italic"
            return "Semibold"
        if self.italic:
            return "Italic"
        return "Regular"


class Theme:
    """
    Defines a font and other theme specific related information.
    """

    @classmethod
    def apply_to(cls, lexer):
        # Apply a font for all styles
        lexer.setFont(Font().load())

        for name, font in cls.__dict__.items():
            if not isinstance(font, Font):
                continue
            style_num = getattr(lexer, name)
            lexer.setColor(QColor(font.color), style_num)
            lexer.setEolFill(True, style_num)
            lexer.setPaper(QColor(font.paper), style_num)
            lexer.setFont(font.load(), style_num)


class DayTheme(Theme):
    """
    Defines a Python related theme including the various font colours for
    syntax highlighting.

    This is a light theme.
    """

    FunctionMethodName = ClassName = Font(color='#0000a0')
    UnclosedString = Font(paper='#FFDDDD')
    Comment = CommentBlock = Font(color='gray')
    Keyword = Font(color='#008080', bold=True)
    SingleQuotedString = DoubleQuotedString = Font(color='#800000')
    TripleSingleQuotedString = TripleDoubleQuotedString = Font(color='#060')
    Number = Font(color='#00008B')
    Decorator = Font(color='#cc6600')
    Default = Identifier = Font()
    Operator = Font(color='#400040')
    HighlightedIdentifier = Font(color='#0000a0')
    Paper = QColor('white')
    Caret = QColor('black')
    Margin = QColor('#EEE')
    Indicator = QColor('red')


class NightTheme(Theme):
    """
    Defines a Python related theme including the various font colours for
    syntax highlighting.

    This is the dark / high contrast theme.
    """

    FunctionMethodName = ClassName = Font(color='#AAA', paper='black')
    UnclosedString = Font(paper='#666')
    Comment = CommentBlock = Font(color='#AAA', paper='black')
    Keyword = Font(color='#EEE', bold=True, paper='black')
    SingleQuotedString = DoubleQuotedString = Font(color='#AAA', paper='black')
    TripleSingleQuotedString = TripleDoubleQuotedString = Font(color='#AAA',
                                                               paper='black')
    Number = Font(color='#AAA', paper='black')
    Decorator = Font(color='#cccccc', paper='black')
    Default = Identifier = Font(color='#fff', paper='black')
    Operator = Font(color='#CCC', paper='black')
    HighlightedIdentifier = Font(color='#ffffff', paper='black')
    Paper = QColor('black')
    Caret = QColor('white')
    Margin = QColor('#333')
    Indicator = QColor('white')


class PythonLexer(QsciLexerPython):
    """
    A Python specific "lexer" that's used to identify keywords of the Python
    language so the editor can do syntax highlighting.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setHighlightSubidentifiers(False)

    def keywords(self, flag):
        """
        Returns a list of Python keywords.
        """
        if flag == 1:
            kws = keyword.kwlist + ['self', 'cls']
        elif flag == 2:
            kws = __builtins__.keys()
        else:
            return None
        return ' '.join(kws)


class EditorPane(QsciScintilla):
    """
    Represents the text editor.
    """

    def __init__(self, path, text, api=None):
        super().__init__()
        self.path = path
        self.setText(text)
        self.indicators = {}
        self.INDICATOR_NUMBER = 19  # arbitrary
        self.MARKER_NUMBER = 22  # also arbitrary
        self.api = api if api else []
        self.setModified(False)
        self.configure()

    def configure(self):
        """
        Set up the editor component.
        """
        # Font information

        font = Font().load()
        self.setFont(font)
        # Generic editor settings
        self.setUtf8(True)
        self.setAutoIndent(True)
        self.setIndentationsUseTabs(False)
        self.setIndentationWidth(4)
        self.setTabWidth(4)
        self.setEdgeColumn(79)
        self.setMarginLineNumbers(0, True)
        self.setMarginWidth(0, 50)
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)
        self.set_theme()
        self.markerDefine(self.RightArrow, self.MARKER_NUMBER)
        self.setMarginSensitivity(1, True)
        self.marginClicked.connect(self.on_marker_clicked)
        self.setAnnotationDisplay(self.AnnotationBoxed)

    def set_theme(self, theme=DayTheme):
        """
        Connect the theme to a lexer and return the lexer for the editor to
        apply to the script text.
        """
        self.lexer = PythonLexer()
        theme.apply_to(self.lexer)
        self.lexer.setDefaultPaper(theme.Paper)
        self.setCaretForegroundColor(theme.Caret)
        self.setMarginsBackgroundColor(theme.Margin)
        self.setMarginsForegroundColor(theme.Caret)
        self.setIndicatorForegroundColor(theme.Indicator)
        self.setMarkerBackgroundColor(theme.Indicator, self.MARKER_NUMBER)

        api = QsciAPIs(self.lexer)
        for entry in self.api:
            api.add(entry)
        api.prepare()
        self.setAutoCompletionThreshold(2)
        self.setAutoCompletionSource(QsciScintilla.AcsAll)

        self.setLexer(self.lexer)

    @property
    def label(self):
        """
        The label associated with this editor widget (usually the filename of
        the script we're editing).

        If the script has been modified since it was last saved, the label will
        end with an asterisk.
        """
        if self.path:
            label = os.path.basename(self.path)
        else:
            label = 'untitled'
        # Add an asterisk to indicate that the file remains unsaved.
        if self.isModified():
            return label + ' *'
        else:
            return label

    def reset_annotations(self):
        """
        Clears all the assets (indicators, annotations and markers) associated
        with last code check.
        """
        self.clearAnnotations()
        self.markerDeleteAll()
        for line_no in self.indicators:
            self.clearIndicatorRange(line_no, 0, line_no, 999999,
                                     self.INDICATOR_NUMBER)
        self.indicators = {}

    def annotate_code(self, feedback):
        """
        Given a list of annotations add them to the editor pane so the user
        can act upon them.
        """
        self.indicatorDefine(self.SquiggleIndicator, self.INDICATOR_NUMBER)
        self.setIndicatorDrawUnder(True)
        for line_no, messages in feedback.items():
            marker_id = self.markerAdd(line_no, self.MARKER_NUMBER)
            col_start = 0
            col_end = 0
            self.indicators[marker_id] = messages
            for message in messages:
                col = message.get('column', 0)
                if col:
                    col_start = col - 1
                    col_end = col + 1
                    self.fillIndicatorRange(line_no, col_start, line_no,
                                            col_end, self.INDICATOR_NUMBER)

    def on_marker_clicked(self, margin, line, state):
        """
        Display something when the margin indicator is clicked.
        """
        marker_id = self.get_marker_at_line(line)
        if marker_id:
            if self.annotation(line):
                self.clearAnnotations(line)
            else:
                messages = [i['message'] for i in
                            self.indicators.get(marker_id, [])]
                text = '\n'.join(messages).strip()
                if text:
                    self.annotate(line, text, self.annotationDisplay())

    def get_marker_at_line(self, line):
        """
        Given a line, will return the marker if one exists. Otherwise, returns
        None.

        Required because the built in markersAtLine method is useless, misnamed
        and doesn't return anything useful. :-(
        """
        for marker_id in self.indicators:
            if self.markerLine(marker_id) == line:
                return marker_id

class FSButtonBar(QToolBar):
    """
    Represents the bar of buttons for file system navigation.
    """
    
    def __init__(self, objectName):
        super().__init__()
        self.slots = {}
        self.setMovable(False)
        self.setIconSize(QSize(8, 8))
        self.setToolButtonStyle(3)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.setObjectName(objectName)    
        
        self.addAction(name="home",
                       tool_text="Go Back to Home Directory")
        self.addAction(name="up", tool_text="Go Up a Level")            
        
    def addAction(self, name, tool_text):
        """
        Creates an action associated with an icon and name and adds it to the
        widget's slots.
        """
        action = QAction(load_icon(name), name.capitalize(), self,
                         toolTip=tool_text)
        super().addAction(action)
        self.slots[name] = action

    def connect(self, name, handler, *shortcuts):
        """
        Connects a named slot to a handler function and optional hot-key
        shortcuts.
        """
        self.slots[name].pyqtConfigure(triggered=handler)
        for shortcut in shortcuts:
            QShortcut(QKeySequence(shortcut),
                      self.parentWidget()).activated.connect(handler)        

class ButtonBar(QToolBar):
    """
    Represents the bar of buttons across the top of the editor and defines
    their behaviour.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.slots = {}

        self.setMovable(False)
        self.setIconSize(QSize(64, 64))
        self.setToolButtonStyle(3)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.setObjectName("StandardToolBar")

        self.addAction(name="new",
                       tool_text="Create a new MicroPython script.")
        self.addAction(name="load", tool_text="Load a MicroPython script.")
        self.addAction(name="save",
                       tool_text="Save the current MicroPython script.")
        self.addSeparator()
        self.addAction(name="flash",
                       tool_text="Flash your code onto the micro:bit.")
        self.addAction(name="files",
                       tool_text="Access the file system on the micro:bit.")
        self.addAction(name="repl",
                       tool_text="Use the REPL to live code the micro:bit.")
        self.addSeparator()
        self.addAction(name="zoom-in",
                       tool_text="Zoom in (to make the text bigger).")
        self.addAction(name="zoom-out",
                       tool_text="Zoom out (to make the text smaller).")
        self.addAction(name="theme",
                       tool_text="Change theme between day or night.")
        self.addSeparator()
        self.addAction(name="check",
                       tool_text="Check your code for mistakes.")
        self.addAction(name="help",
                       tool_text="Show help about Mu in a browser.")
        self.addAction(name="quit", tool_text="Quit Mu.")

    def addAction(self, name, tool_text):
        """
        Creates an action associated with an icon and name and adds it to the
        widget's slots.
        """
        action = QAction(load_icon(name), name.capitalize(), self,
                         toolTip=tool_text)
        super().addAction(action)
        self.slots[name] = action

    def connect(self, name, handler, *shortcuts):
        """
        Connects a named slot to a handler function and optional hot-key
        shortcuts.
        """
        self.slots[name].pyqtConfigure(triggered=handler)
        for shortcut in shortcuts:
            QShortcut(QKeySequence(shortcut),
                      self.parentWidget()).activated.connect(handler)


class FileTabs(QTabWidget):
    """
    Extend the base class so we can override the removeTab behaviour.
    """

    def __init__(self):
        super(FileTabs, self).__init__()
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.removeTab)

    def removeTab(self, tab_id):
        """
        Ask the user before closing the file.
        """
        window = self.nativeParentWidget()
        modified = window.current_tab.isModified()
        if (modified):
            msg = 'There is un-saved work, closing the tab will cause you ' \
                  'to lose it.'
            if window.show_confirmation(msg) == QMessageBox.Cancel:
                return
        super(FileTabs, self).removeTab(tab_id)


class Window(QStackedWidget):
    """
    Defines the look and characteristics of the application's main window.
    """

    title = "Mu"
    icon = "icon"

    _zoom_in = pyqtSignal(int)
    _zoom_out = pyqtSignal(int)
    
    fs = None
    repl = None
    
    fs_splitter_index = None    # splitter index of fs widget for restoration
    repl_splitter_index = None  # splitter index of repl for widget restoration
    
    # save the state so size changes persists
    fs_splitter_state = None    
    repl_splitter_state = None

    def set_clipboard(self, clipboard):
        self.clipboard = clipboard

    def zoom_in(self):
        """
        Handles zooming in.
        """
        self._zoom_in.emit(2)

    def zoom_out(self):
        """
        Handles zooming out.
        """
        self._zoom_out.emit(2)

    def connect_zoom(self, widget):
        """
        Connects a referenced widget to the zoom related signals.
        """
        self._zoom_in.connect(widget.zoomIn)
        self._zoom_out.connect(widget.zoomOut)

    @property
    def current_tab(self):
        """
        Returns the currently focussed tab.
        """
        return self.tabs.currentWidget()

    def get_load_path(self, folder):
        """
        Displays a dialog for selecting a file to load. Returns the selected
        path. Defaults to start in the referenced folder.
        """
        path, _ = QFileDialog.getOpenFileName(self.widget, 'Open file', folder,
                                              '*.py *.hex')
        logger.debug('Getting load path: {}'.format(path))
        return path

    def get_save_path(self, folder):
        """
        Displays a dialog for selecting a file to save. Returns the selected
        path. Defaults to start in the referenced folder.
        """
        path, _ = QFileDialog.getSaveFileName(self.widget, 'Save file', folder)
        logger.debug('Getting save path: {}'.format(path))
        return path

    def get_microbit_path(self, folder):
        """
        Displays a dialog for locating the location of the BBC micro:bit in the
        host computer's filesystem. Returns the selected path. Defaults to
        start in the referenced folder.
        """
        path = QFileDialog.getExistingDirectory(self.widget,
                                                'Locate BBC micro:bit', folder,
                                                QFileDialog.ShowDirsOnly)
        logger.debug('Getting micro:bit path: {}'.format(path))
        return path

    def add_tab(self, path, text):
        """
        Adds a tab with the referenced path and text to the editor.
        """
        new_tab = EditorPane(path, text, self.api)
        new_tab_index = self.tabs.addTab(new_tab, new_tab.label)

        @new_tab.modificationChanged.connect
        def on_modified():
            self.tabs.setTabText(new_tab_index, new_tab.label)

        self.tabs.setCurrentIndex(new_tab_index)
        self.connect_zoom(new_tab)
        self.set_theme(self.theme)
        new_tab.setFocus()

    @property
    def tab_count(self):
        """
        Returns the number of active tabs.
        """
        return self.tabs.count()

    @property
    def widgets(self):
        """
        Returns a list of references to the widgets representing tabs in the
        editor.
        """
        return [self.tabs.widget(i) for i in range(self.tab_count)]

    @property
    def modified(self):
        """
        Returns a boolean indication if there are any modified tabs in the
        editor.
        """
        for widget in self.widgets:
            if widget.isModified():
                return True
        return False

    def add_filesystem(self, home):
        """
        Adds the file system pane to the application.
        """
        # passing reference to self so LocalFileList can open a tab with a 
        # double-click
        self.fs = FileSystemPane(self.splitter, home, self)
        self.splitter.addWidget(self.fs)
        # save the index of the fs pane
        self.fs_splitter_index = self.splitter.indexOf(self.fs)
        
        if self.splitter.count() == 2:
            self.splitter.setSizes([66, 33])
        else:
            self.splitter.setSizes([66, 0, 33])
            
        self.fs.setFocus()
        self.connect_zoom(self.fs)
        
        # FileSystem pane is being created at startup now so hide this 
        # pane
        self.hide_fs()


    def add_repl(self, mb_port):
        """
        Adds the REPL pane to the application.
        """
        
        self.repl = REPLPane(port=mb_port, clipboard=self.clipboard, theme=self.theme)
        self.splitter.addWidget(self.repl)
        self.repl_splitter_index = self.splitter.indexOf(self.repl)
        if self.splitter.count() == 2:
            self.splitter.setSizes([66, 33])
        else:
            self.splitter.setSizes([66, 0, 33])
            
        self.repl.setFocus()
        self.connect_zoom(self.repl)
        
        # REPL is being created at startup now so hide the pane and
        # disonnect the session.
        self.hide_repl()
            
    def hide_repl(self):            
        self.repl_splitter_state = self.splitter.saveState()
        # self.repl.close()
        self.repl.hide()
        self.repl.active = False
        logger.debug("Hiding the REPL Editor")
        
    def show_repl(self):
        # if microbit serial is connected, close before opening REPL connection
        if self.fs.microbit_fs.connected:
            self.fs.microbit_fs.close_serial()
                    
        if not self.repl.connected:
            self.repl.connect()
            
        self.splitter.restoreState(self.repl_splitter_state)
        self.repl.show()
        self.repl.active = True
        self.repl.setFocus()
        logger.debug("Showing REPL Editor")
        
    def hide_fs(self):
        # save the splitter state for when we restore the fs pane
        self.fs_splitter_state = self.splitter.saveState()
        self.fs.hide()
        self.fs.active = False
        logger.debug("Hiding the FS Pane")
        
    def show_fs(self):        
        # if the REPL is connected, close before opening a microfs connection
        if self.repl.connected:
            self.repl.close()
            
        if not self.fs.microbit_fs.connected:
            self.fs.microbit_fs.open_serial()
            
        self.splitter.restoreState(self.fs_splitter_state)
        self.fs.show()
        self.fs.setFocus()
        self.fs.active = True      
        logger.debug("Showing the FS Pane")

    def set_theme(self, theme):
        """
        Sets the theme for the REPL and editor tabs.
        """
        self.setStyleSheet(DAY_STYLE)
        self.theme = theme
        new_theme = DayTheme
        new_icon = 'theme'
        if theme == 'night':
            new_theme = NightTheme
            new_icon = 'theme_day'
            self.setStyleSheet(NIGHT_STYLE)
        for widget in self.widgets:
            widget.set_theme(new_theme)
        self.button_bar.slots['theme'].setIcon(load_icon(new_icon))
        if hasattr(self, 'repl') and self.repl:
            self.repl.set_theme(theme)

    def show_message(self, message, information=None, icon=None, parent=None):
        """
        Displays a modal message to the user.

        If information is passed in this will be set as the additional
        informative text in the modal dialog.

        Since this mechanism will be used mainly for warning users that
        something is awry the default icon is set to "Warning". It's possible
        to override the icon to one of the following settings: NoIcon,
        Question, Information, Warning or Critical.
        """
        message_box = QMessageBox(parent)
        message_box.setText(message)
        message_box.setWindowTitle('Mu')
        if information:
            message_box.setInformativeText(information)
        if icon and hasattr(message_box, icon):
            message_box.setIcon(getattr(message_box, icon))
        else:
            message_box.setIcon(message_box.Warning)
        logger.debug(message)
        logger.debug(information)
        message_box.exec()

    def show_confirmation(self, message, information=None, icon=None, parent=None):
        """
        Displays a modal message to the user to which they need to confirm or
        cancel.

        If information is passed in this will be set as the additional
        informative text in the modal dialog.

        Since this mechanism will be used mainly for warning users that
        something is awry the default icon is set to "Warning". It's possible
        to override the icon to one of the following settings: NoIcon,
        Question, Information, Warning or Critical.
        """
        message_box = QMessageBox(parent)
        message_box.setText(message)
        message_box.setWindowTitle('Mu')
        if information:
            message_box.setInformativeText(information)
        if icon and hasattr(message_box, icon):
            message_box.setIcon(getattr(message_box, icon))
        else:
            message_box.setIcon(message_box.Warning)
        message_box.setStandardButtons(message_box.Cancel | message_box.Ok)
        message_box.setDefaultButton(message_box.Cancel)
        logger.debug(message)
        logger.debug(information)
        return message_box.exec()

    def update_title(self, filename=None):
        """
        Updates the title bar of the application. If a filename (representing
        the name of the file currently the focus of the editor) is supplied,
        append it to the end of the title.
        """
        title = self.title
        if filename:
            title += ' - ' + filename
        self.setWindowTitle(title)

    def autosize_window(self):
        """
        Makes the editor 80% of the width*height of the screen and centres it.
        """
        screen = QDesktopWidget().screenGeometry()
        w = int(screen.width() * 0.8)
        h = int(screen.height() * 0.8)
        self.resize(w, h)
        size = self.geometry()
        self.move((screen.width() - size.width()) / 2,
                  (screen.height() - size.height()) / 2)

    def reset_annotations(self):
        """
        Resets the state of annotations on the current tab.
        """
        self.current_tab.reset_annotations()

    def annotate_code(self, feedback):
        """
        Given a list of annotations about the code in the current tab, add
        the annotations to the editor window so the user can make appropriate
        changes.
        """
        self.current_tab.annotate_code(feedback)

    def setup(self, theme, api=None):
        """
        Sets up the window.

        Defines the various attributes of the window and defines how the user
        interface is laid out.
        """
        self.theme = theme
        self.api = api if api else []
        # Give the window a default icon, title and minimum size.
        self.setWindowIcon(load_icon(self.icon))
        self.update_title()
        self.setMinimumSize(926, 600)

        self.widget = QWidget()


        self.splitter = QSplitter(Qt.Vertical)
        
        widget_layout = QVBoxLayout()
        self.widget.setLayout(widget_layout)

        self.button_bar = ButtonBar(self.widget)

        widget_layout.addWidget(self.button_bar)
        widget_layout.addWidget(self.splitter)
        self.tabs = FileTabs()
        self.splitter.addWidget(self.tabs)

        self.addWidget(self.widget)
        self.setCurrentWidget(self.widget)

        self.set_theme(theme)
        self.show()
        self.autosize_window()


class REPLPane(QTextEdit):
    """
    REPL = Read, Evaluate, Print, Loop.

    This widget represents a REPL client connected to a BBC micro:bit running
    MicroPython.

    The device MUST be flashed with MicroPython for this to work.
    """

    def __init__(self, port, clipboard, theme='day', parent=None):
        super().__init__(parent)
        self.clipboard = clipboard
        self.port = port
        self.setFont(Font().load())
        self.setAcceptRichText(False)
        self.setReadOnly(False)
        self.setObjectName('replpane')
        # open the serial port
        self.serial = QSerialPort(self)
        self.serial.setPortName(port)
        self.connect()
        self.connected = True
        self.active = True
        self.set_theme(theme)
               
    def connect(self):
        if self.serial.open(QIODevice.ReadWrite):
            self.serial.setBaudRate(115200)
            self.serial.readyRead.connect(self.on_serial_read)
            # clear the text
            self.clear()
            # Send a Control-C
            self.serial.write(b'\x03')
            self.connected = True
        else:
            port_name = self.serial.portName()
            raise IOError("Cannot connect to device on port {}".format(self.port))     
        
    def close(self):
        self.serial.close()
        self.connected = False
        logger.debug("REPL closing connection to {}".format(self.port))
        
    def soft_reboot(self):
        self.serial.write(b'\x04')
        logger.debug("REPL sending soft reboot to {}".format(self.port))
        
    def set_theme(self, theme):
        """
        Sets the theme / look for the REPL pane.
        """
        if theme == 'day':
            self.setStyleSheet(DAY_STYLE)
        else:
            self.setStyleSheet(NIGHT_STYLE)

    def on_serial_read(self):
        """
        Called when the application gets data from the connected device.
        """
        self.process_bytes(bytes(self.serial.readAll()))

    def keyPressEvent(self, data):
        """
        Called when the user types something in the REPL.

        Correctly encodes it and sends it to the connected device.
        """
        key = data.key()
        msg = bytes(data.text(), 'utf8')

        if key == Qt.Key_Backspace:
            msg = b'\b'
        elif key == Qt.Key_Up:
            msg = b'\x1B[A'
        elif key == Qt.Key_Down:
            msg = b'\x1B[B'
        elif key == Qt.Key_Right:
            msg = b'\x1B[C'
        elif key == Qt.Key_Left:
            msg = b'\x1B[D'
        elif data.modifiers() == Qt.ControlModifier:
        #     # Handle the Control key.  I would've expected us to have to test
        #     # for Qt.ControlModifier, but on (my!) OSX Qt.MetaModifier does
        #     # correspond to the Control key.  I've read something that suggests
        #     # that it's different on other platforms.
        #     # see http://doc.qt.io/qt-5/qt.html#KeyboardModifier-enum
            if key == Qt.Key_V:
                msg = self.clipboard.text()
            elif Qt.Key_A <= key <= Qt.Key_Z:
        #         # The microbit treats an input of \x01 as Ctrl+A, etc.
                 msg = bytes([1 + key - Qt.Key_A])
        self.serial.write(msg)

    def process_bytes(self, bs):
        """
        Given some incoming bytes of data, work out how to handle / display
        them in the REPL widget.
        """
        tc = self.textCursor()
        logger.debug(bs)
        # The text cursor must be on the last line of the document. If it isn't
        # then move it there.
        while tc.movePosition(QTextCursor.Down):
            pass
        i = 0
        while i < len(bs):
            if bs[i] == 8:  # \b
                tc.movePosition(QTextCursor.Left)
                self.setTextCursor(tc)
            elif bs[i] == ord('\r'):
                pass
            elif bs[i] == 0x1b and bs[i+1] == ord('['):  #VT100 cursor control
                i += 2  # move index to after the [
                m = re.search(r'(?P<count>[\d]*)(?P<action>[ABCDK])', bs[i:].decode('ascii', errors='ignore'))
                i += m.end() - 1  #move to (almost) after the control seq (will increment at end of loop)

                if m.group("count") == '':
                    count = 1
                else:
                    count = int(m.group("count"))

                if m.group("action") == "A":  #up
                    tc.movePosition(QTextCursor.Up, n=count)
                    self.setTextCursor(tc)
                elif m.group("action") == "B":  #down
                    tc.movePosition(QTextCursor.Down, n=count)
                    self.setTextCursor(tc)
                elif m.group("action") == "C":  #right
                    tc.movePosition(QTextCursor.Right, n=count)
                    self.setTextCursor(tc)
                elif m.group("action") == "D":  #left
                    tc.movePosition(QTextCursor.Left, n=count)
                    self.setTextCursor(tc)
                elif m.group("action") == "K":  #delete things
                    if m.group("count") == "":  #delete to end of line
                        tc.movePosition(QTextCursor.EndOfLine, mode=QTextCursor.KeepAnchor)
                        tc.removeSelectedText()
                        self.setTextCursor(tc)
            elif bs[i] == ord('\n'):
                tc.movePosition(QTextCursor.End)
                self.setTextCursor(tc)
                self.insertPlainText(chr(bs[i]))
            else:
                tc.deleteChar()
                self.setTextCursor(tc)
                self.insertPlainText(chr(bs[i]))
            i += 1
        self.ensureCursorVisible()

    def clear(self):
        """
        Clears the text of the REPL.
        """
        self.setText('')


class MuFileList(QListWidget):
    """
    Contains shared methods for the two types of file listing used in Mu.
    """
    def disable(self, sibling):
        """
        Stops interaction with the list widgets.
        """
        self.setDisabled(True)
        sibling.setDisabled(True)
        self.setAcceptDrops(False)
        sibling.setAcceptDrops(False)

    def enable(self, sibling):
        """
        Allows interaction with the list widgets.
        """
        self.setDisabled(False)
        sibling.setDisabled(False)
        self.setAcceptDrops(True)
        sibling.setAcceptDrops(True)
        
    def chdirHome(self):
        self.current_dir = self.home
        self.ls()
        
    def chdirUp(self):
        if self.current_dir != self.home:
            new_path = self.current_dir.split("/")[0:-1]
            self.current_dir = "/".join(new_path)
            self.ls()        
            
    def parse_ls(self, files):
        self.clear()
        for f in files:
            item = QListWidgetItem(f[0])
            if f[1] == "D":
                item.setForeground(QColor('blue'))
            else:
                item.setForeground(QColor('green'))
                
            # utilize the QT::UserRole to keep metadata for this file.
            item.setData(256,(f[1], os.path.join(self.current_dir, f[0])))
            
                
            self.addItem(item)        


class MicrobitFileList(MuFileList):
    """
    Represents a list of files on the micro:bit.
    """

    def __init__(self, home, window):
        super().__init__()
        self.window = window
        self.home = microfs.getcwd()
        self.current_dir = self.home
        self.serial = microfs.get_serial()   # get a serial object from microfs
        self.connected = True
        self.setDragDropMode(QListWidget.DragDrop)
        self.itemDoubleClicked.connect(self.itemDoubleClickedEvent)
        
        self.label = QLabel()
        self.label.setText('Files on your device')
        self.toolbar = FSButtonBar("DeviceFS")
        self.toolbar.connect("home", self.chdirHome)
        self.toolbar.connect("up", self.chdirUp)
        
        self.ls()
        
    def open_serial(self):
        """
            connect to the serial port
        """
        self.serial.open()
        self.connected = True
        
    def close_serial(self):
        """
            close the microfs serial port
        """
        self.serial.close()
        self.connected = False
        
    def ls(self):
        microbit_files = microfs.ls2(self.serial, d=self.current_dir)
        microbit_files.sort(key=lambda x: (x[1], x[0]))
        self.parse_ls(microbit_files)

    def dropEvent(self, event):
        source = event.source()
        self.disable(source)
        if isinstance(source, LocalFileList):
            local_filename = source.currentItem().text()
            local_fullpath = source.currentItem().data(256)[1]
             
            if source.currentItem().data(256)[0] == "D":
                head, tail = os.path.split(local_fullpath)
                micro_fullpath = os.path.join(self.current_dir, tail)
                logger.info("Copying {} to {}".format(local_fullpath, 
                                                      micro_fullpath))
                try:
                    ucopytree(local_fullpath, micro_fullpath, self.serial)
                    super().dropEvent(event)
                except Exception as ex:
                    logger.error(ex)                
            else:
                micro_fullpath = os.path.join(self.current_dir, local_filename)
                logger.info("Copying {} to {}".format(local_fullpath, 
                                                      micro_fullpath))
                try:
                    microfs.put2(local_fullpath, target=micro_fullpath, 
                                 serial=self.serial)
                except Exception as ex:
                    logger.error(ex)                    

            self.ls()
        self.enable(source)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        delete_action = menu.addAction("Delete (cannot be undone)")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == delete_action:
            self.setDisabled(True)
            self.setAcceptDrops(False)
            
            dir_or_file = self.currentItem().data(256)[1]
            try:
                if self.currentItem().data(256)[0] == "D":
                    urmtree(dir_or_file, self.serial)
                else:
                    microfs.rm(self.serial, dir_or_file)
                self.takeItem(self.currentRow())
                
                logger.info("Deleting {}".format(microbit_filename))
            except Exception as ex:
                logger.error(ex)
            self.setDisabled(False)
            self.setAcceptDrops(True)
            
    def itemDoubleClickedEvent(self, event):
        item = self.currentItem()
        if item.data(256)[0] == "F":
            pass
        else:
            # directory; get new listing
            d = item.text()
            self.current_dir += "/" + d
            self.ls()       


class LocalFileList(MuFileList):
    """
    Represents a list of files in the Mu directory on the local machine.
    """

    def __init__(self, home, window):
        super().__init__()
        self.window = window
        self.home = home
        self.current_dir = self.home
        self.setDragDropMode(QListWidget.DragDrop)
        self.label = QLabel()
        self.label.setText('Files on your Computer')
        
        self.itemDoubleClicked.connect(self.itemDoubleClickedEvent)
        
        self.toolbar = FSButtonBar("LocalFS")
        self.toolbar.connect("home", self.chdirHome)
        self.toolbar.connect("up", self.chdirUp)        
        
        self.ls()
        
    def ls(self):
        local_files = []
        for f in os.listdir(self.current_dir):
            full_path = os.path.join(self.current_dir, f)
            if not f.startswith("."):
                if os.path.isfile(full_path):
                    local_files.append((f, 'F'))
                else:
                    local_files.append((f, 'D'))
                
        local_files.sort(key=lambda x: (x[1], x[0]))
        self.parse_ls(local_files)        

    def dropEvent(self, event):
        source = event.source()
        self.disable(source)
        if isinstance(source, MicrobitFileList):
            microbit_filename = source.currentItem().text()
            microbit_fullpath = source.currentItem().data(256)[1]
            local_fullpath = os.path.join(self.current_dir,
                                          microbit_filename)
            logger.debug("Getting {} to {}".format(microbit_fullpath,
                                                   local_fullpath))
            try:
                with microfs.get_serial() as serial:
                    logger.info(serial.port)
                    microfs.get(serial, microbit_fullpath, target=local_fullpath)
                super().dropEvent(event)
            except Exception as ex:
                logger.error(ex)
        self.ls()
        self.enable(source)
        
    def itemDoubleClickedEvent(self, event):
        """
        Double-Click
        
        """
        item = self.currentItem()
        if item.data(256)[0] == "F":
            # read the file and load it into a tab; a bit duplicative of the
            # load method in logic.Editor
            path = item.data(256)[1]
            logger.info('Loading script from: {}'.format(path))
            try:
                if path.endswith('.py'):
                    # Open the file, read the textual content and set the name as
                    # the path to the file.
                    with open(path) as f:
                        text = f.read()
                    name = path
                else:
                    # Open the hex, extract the Python script therein and set the
                    # name to None, thus forcing the user to work out what to name
                    # the recovered script.
                    with open(path) as f:
                        text = uflash.extract_script(f.read())
                    name = None
            except FileNotFoundError:
                pass
            else:
                logger.debug(text)
                self.window.add_tab(name, text)            
        else:
            # directory; get new listing
            d = item.text()
            self.current_dir += "/" + d
            self.ls()         


class FileSystemPane(QFrame):
    """
    Contains two QListWidgets representing the micro:bit and the user's code
    directory. Users transfer files by dragging and dropping. Highlighted files
    can be selected for deletion.
    """

    def __init__(self, parent, home, window):
        super().__init__(parent)
        self.home = home
        self.font = Font().load()
        self.window = window
        
        self.microbit_fs = MicrobitFileList(home, self.window)
        self.local_fs = LocalFileList(home, self.window)
        
        layout = QGridLayout()
        self.setLayout(layout)
        
        self.set_font_size()
        
        #microbit_fs_bb = FSButtonBar('MicroBit FS')
        local_fs_bb = FSButtonBar('Local FS')
        
        layout.addWidget(self.microbit_fs.label, 0, 0)
        layout.addWidget(self.local_fs.label, 0, 1)
        layout.addWidget(self.microbit_fs.toolbar, 1, 0)
        layout.addWidget(self.local_fs.toolbar, 1, 1)
        layout.addWidget(self.microbit_fs, 2, 0)
        layout.addWidget(self.local_fs, 2, 1)
        
        self.active = True
        

    def set_theme(self, theme):
        """
        Sets the theme / look for the FileSystemPane.
        """
        if theme == 'day':
            self.setStyleSheet(DAY_STYLE)
        else:
            self.setStyleSheet(NIGHT_STYLE)

    def set_font_size(self, new_size=DEFAULT_FONT_SIZE):
        """
        Sets the font size for all the textual elements in this pane.
        """
        self.font.setPointSize(new_size)
        self.microbit_fs.label.setFont(self.font)
        
        self.local_fs.label.setFont(self.font)
        self.microbit_fs.setFont(self.font)
        self.local_fs.setFont(self.font)

    def zoomIn(self, delta=2):
        """
        Zoom in (increase) the size of the font by delta amount difference in
        point size upto 34 points.
        """
        old_size = self.font.pointSize()
        new_size = min(old_size + delta, 34)
        self.set_font_size(new_size)

    def zoomOut(self, delta=2):
        """
        Zoom out (decrease) the size of the font by delta amount difference in
        point size down to 4 points.
        """
        old_size = self.font.pointSize()
        new_size = max(old_size - delta, 4)
        self.set_font_size(new_size)
        

