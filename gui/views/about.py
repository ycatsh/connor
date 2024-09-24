from PyQt6.QtWidgets import QVBoxLayout, QLabel, QDialog, QTextEdit

class About(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Tutorial")
        self.setFixedSize(600, 450)
        self.setModal(True)

        # Layout
        layout = QVBoxLayout()
        section = QVBoxLayout()

        # Section 1
        title_lft = QLabel("<h2>Select Folder</h2>")
        desc_lft = QTextEdit()
        desc_lft.setHtml("""
            <p>Allows you to select a folder on your computer and organize it using artificial intelligence based on the content or the names of the files.</p>
            <p>After selecting or entering the absolute path of the folder in the appropriate screen, click on <strong>ORGANIZE FILES</strong> to start the organization process.</p>
        """)
        desc_lft.setReadOnly(True)
        desc_lft.setFixedSize(575, 100)

        title_rgt = QLabel("<h2>Upload Files</h2>")
        desc_rgt = QTextEdit()
        desc_rgt.setHtml("""
            <style>
            code {
                font-family: Monospace;
                color: #75a7ad;
                background-color: #202020;
                padding: 2px;
                font-size: 105%;
            }
            </style>
            <p>Allows you to upload files manually from anywhere on your computer.</p>
            <p>After going to the appropriate screen, click on <strong>UPLOAD FILES</strong> to manually upload files into the app. These files are stored temporarily in <code>tmp/</code> in the app's root directory for the purpose of organization.</p>
            <p>You can also choose between copying or moving the files:</p>
            <ul>
                <li><strong>Copy Files:</strong> copies the files from the original location into the app</li>
                <li><strong>Move Files:</strong> moves the files from the original location into the app</li>
            </ul>
            <p>After you have ensured the files are uploaded into the app, click on <strong>ORGANIZE FILES</strong> to organize the uploaded files into a folder. Upon completion, you can send the organized folder containing your uploaded files (but organized using artificial intelligence) back to anywhere on your computer by clicking on <strong>SEND TO COMPUTER</strong>.</p>
        """)
        desc_rgt.setReadOnly(True)
        desc_rgt.setFixedSize(575, 240)

        section.addWidget(title_lft)
        section.addWidget(desc_lft)
        section.addWidget(title_rgt)
        section.addWidget(desc_rgt)

        layout.addLayout(section)
        self.setLayout(layout)
