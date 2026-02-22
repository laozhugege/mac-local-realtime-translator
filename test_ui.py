import sys
from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

class SubtitleWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Prevent stealing focus from other apps
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.label = QLabel("等待翻译中...", self)
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 150);
                font-size: 24px;
                padding: 10px;
                border-radius: 10px;
            }
        """)

        # Calculate initial position (bottom center)
        screen = QApplication.primaryScreen().geometry()
        width = 800
        height = 60
        x = (screen.width() - width) // 2
        y = screen.height() - height - 100
        
        self.setGeometry(x, y, width, height)
        self.label.setGeometry(0, 0, width, height)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.oldPos = self.pos()

    def update_text(self, text):
        if text.strip():
            self.label.setText(text)

    # Enable Dragging
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.pos() + delta)
            self.oldPos = event.globalPosition().toPoint()

class TranslatorThread(QThread):
    text_ready = pyqtSignal(str)

    def run(self):
        import time
        # Simulate translations coming in
        test_sentences = [
            "这是翻译测试的第一句。",
            "你现在可以任意拖动这个窗口。",
            "试着点击背后的其他软件...",
            "你会发现它不会抢夺焦点。",
            "且它会永远保持在最顶层显示。",
            "测试完毕！按 Ctrl+C 退出主程序。"
        ]
        for sentence in test_sentences:
            time.sleep(3)
            self.text_ready.emit(sentence)

def main():
    app = QApplication(sys.argv)
    
    window = SubtitleWindow()
    window.show()

    # Start dummy translator thread
    thread = TranslatorThread()
    thread.text_ready.connect(window.update_text)
    thread.start()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
