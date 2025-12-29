import sys
import os
import io
from contextlib import redirect_stdout
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QSpinBox, QGroupBox, QMessageBox, QProgressBar, QCheckBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTextStream
from PyQt5.QtGui import QFont
import traceback

# Import the scraper
from scraper import HomeAdvisorScraper


class ScraperThread(QThread):
    """Thread to run the scraper without freezing the GUI"""
    progress_signal = pyqtSignal(str)  # For progress messages
    error_signal = pyqtSignal(str)  # For error messages
    finished_signal = pyqtSignal(int)  # For completion (number of businesses)
    
    def __init__(self, base_url, start_page, google_sheet_id, credentials_file, headless=True, captcha_api_key=None):
        super().__init__()
        self.base_url = base_url
        self.start_page = start_page
        self.google_sheet_id = google_sheet_id
        self.credentials_file = credentials_file
        self.headless = headless
        self.captcha_api_key = captcha_api_key
        self.scraper = None
        self._is_running = True
    
    def run(self):
        """Run the scraper in this thread"""
        try:
            self.progress_signal.emit("Initializing scraper...")
            
            if not os.path.exists(self.credentials_file):
                self.error_signal.emit(f"ERROR: {self.credentials_file} not found!")
                return
            
            self.scraper = HomeAdvisorScraper(
                self.base_url, 
                self.google_sheet_id, 
                self.credentials_file, 
                headless=self.headless,
                captcha_api_key=self.captcha_api_key
            )
            
            self.progress_signal.emit("Detecting total number of pages...")
            total_pages = self.scraper.detect_total_pages()
            
            if total_pages == 0:
                self.error_signal.emit("ERROR: Could not detect any pages. Please check the URL.")
                return
            
            self.progress_signal.emit(f"Found {total_pages} pages to scrape")
            self.progress_signal.emit(f"Starting from page {self.start_page}")
            
            # Check if headers exist, add them if not
            try:
                all_values = self.scraper.sheet.get_all_values()
                headers_exist = False
                if all_values and len(all_values) > 0:
                    first_row = [str(v).lower().strip() for v in all_values[0]]
                    if 'business name' in first_row or 'businessname' in ''.join(first_row).lower():
                        headers_exist = True
                
                if not headers_exist:
                    self.progress_signal.emit("Initializing Google Sheet with headers...")
                    headers = ['business name', 'star rating', '# of reviews', 'address', 'website', 'Phone Number', 'Email']
                    # Only add headers if sheet is empty or doesn't have headers
                    if not all_values or len(all_values) == 0:
                        self.scraper.sheet.append_row(headers)
                        self.progress_signal.emit("Sheet initialized with headers")
                    else:
                        # Insert headers at the beginning
                        self.scraper.sheet.insert_row(headers, 1)
                        self.progress_signal.emit("Added headers to sheet")
                else:
                    self.progress_signal.emit("Sheet already has headers, continuing...")
            except Exception as e:
                self.progress_signal.emit(f"⚠️  Warning: Could not check/add headers: {e}")
                # Try to add headers anyway if sheet is empty
                try:
                    all_values = self.scraper.sheet.get_all_values()
                    if not all_values or len(all_values) == 0:
                        headers = ['business name', 'star rating', '# of reviews', 'address', 'website', 'Phone Number', 'Email']
                        self.scraper.sheet.append_row(headers)
                        self.progress_signal.emit("Sheet initialized with headers")
                except:
                    pass
            
            # Create a custom stdout that emits signals
            class SignalEmitter:
                def __init__(self, signal):
                    self.signal = signal
                
                def write(self, text):
                    if text.strip():  # Only emit non-empty lines
                        # Split by newlines and emit each line
                        for line in text.rstrip().split('\n'):
                            if line.strip():
                                self.signal.emit(line)
                    return len(text)
                
                def flush(self):
                    pass
                
                def isatty(self):
                    return False
            
            # Redirect stdout to capture print statements
            emitter = SignalEmitter(self.progress_signal)
            old_stdout = sys.stdout
            sys.stdout = emitter
            
            try:
                self.progress_signal.emit(f"\n{'='*60}")
                self.progress_signal.emit(f"Starting to scrape {total_pages} pages")
                self.progress_signal.emit(f"{'='*60}\n")
                
                # Scrape all pages
                businesses = self.scraper.scrape_all_pages(total_pages=total_pages, start_page=self.start_page)
                
                self.progress_signal.emit(f"\n{'='*50}")
                self.progress_signal.emit(f"Scraping complete! Total businesses: {len(businesses)}")
                self.progress_signal.emit(f"{'='*50}")
                
                self.finished_signal.emit(len(businesses))
            finally:
                # Restore stdout
                sys.stdout = old_stdout
            
        except Exception as e:
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            self.error_signal.emit(error_msg)
        finally:
            if self.scraper:
                self.scraper.close()
    
    def stop(self):
        """Stop the scraper"""
        self._is_running = False
        if self.scraper:
            self.scraper.close()


class ScraperGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.scraper_thread = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("HomeAdvisor Scraper")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title
        title = QLabel("HomeAdvisor Scraper")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Configuration group
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout()
        
        # URL input
        url_layout = QHBoxLayout()
        url_label = QLabel("HomeAdvisor URL:")
        url_label.setMinimumWidth(150)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.homeadvisor.com/c.Air-Conditioning.Elizabeth.NJ.-12002.html")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        config_layout.addLayout(url_layout)
        
        # Start page input
        page_layout = QHBoxLayout()
        page_label = QLabel("Start from page:")
        page_label.setMinimumWidth(150)
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(10000)
        self.page_spinbox.setValue(1)
        page_layout.addWidget(page_label)
        page_layout.addWidget(self.page_spinbox)
        page_layout.addStretch()
        config_layout.addLayout(page_layout)
        
        # Headless mode checkbox
        headless_layout = QHBoxLayout()
        self.headless_checkbox = QCheckBox("Run in headless mode (no browser window)")
        self.headless_checkbox.setChecked(True)
        headless_layout.addWidget(self.headless_checkbox)
        headless_layout.addStretch()
        config_layout.addLayout(headless_layout)
        
        # CAPTCHA API Key input (optional)
        captcha_layout = QHBoxLayout()
        captcha_label = QLabel("2Captcha API Key:")
        captcha_label.setMinimumWidth(150)
        self.captcha_input = QLineEdit()
        self.captcha_input.setPlaceholderText("Optional - for automatic CAPTCHA solving")
        self.captcha_input.setEchoMode(QLineEdit.Password)  # Hide the API key
        # Try to get from environment variable
        import os
        env_key = os.getenv('CAPTCHA_API_KEY')
        if env_key:
            self.captcha_input.setText(env_key)
        captcha_layout.addWidget(captcha_label)
        captcha_layout.addWidget(self.captcha_input)
        config_layout.addLayout(captcha_layout)
        
        # Add info label about 2Captcha
        captcha_info = QLabel("💡 Get API key from <a href='https://2captcha.com/'>2captcha.com</a> (optional)")
        captcha_info.setOpenExternalLinks(True)
        captcha_info.setStyleSheet("color: #666; font-size: 9pt;")
        config_layout.addWidget(captcha_info)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Scraping")
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.start_button.clicked.connect(self.start_scraping)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_scraping)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Log output
        log_group = QGroupBox("Progress Log")
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Add some default text
        self.log_output.append("Welcome to HomeAdvisor Scraper!")
        self.log_output.append("Enter a HomeAdvisor URL and click 'Start Scraping' to begin.")
        self.log_output.append("")
    
    def log_message(self, message):
        """Add a message to the log output"""
        self.log_output.append(message)
        # Auto-scroll to bottom
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )
    
    def start_scraping(self):
        """Start the scraping process"""
        url = self.url_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a HomeAdvisor URL!")
            return
        
        if not url.startswith('http'):
            url = 'https://' + url
        
        start_page = self.page_spinbox.value()
        headless = self.headless_checkbox.isChecked()
        captcha_api_key = self.captcha_input.text().strip() or None
        
        # Configuration
        GOOGLE_SHEET_ID = "1b8JUs4vGZXY7YTnmPJ9KEUqDzXufmRuRBL2u5i6NPx4"
        CREDENTIALS_FILE = "homeadvisorelizabethscraping-613984138d99.json"
        
        # Disable start button, enable stop button
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("Scraping in progress...")
        
        # Clear log
        self.log_output.clear()
        self.log_message(f"Starting scraper with URL: {url}")
        self.log_message(f"Starting from page: {start_page}")
        self.log_message(f"Headless mode: {headless}")
        self.log_message("")
        
        # Create and start scraper thread
        self.scraper_thread = ScraperThread(
            url, 
            start_page, 
            GOOGLE_SHEET_ID, 
            CREDENTIALS_FILE, 
            headless=headless,
            captcha_api_key=captcha_api_key
        )
        self.scraper_thread.progress_signal.connect(self.log_message)
        self.scraper_thread.error_signal.connect(self.handle_error)
        self.scraper_thread.finished_signal.connect(self.scraping_finished)
        self.scraper_thread.start()
    
    def stop_scraping(self):
        """Stop the scraping process"""
        if self.scraper_thread and self.scraper_thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "Stop Scraping", 
                "Are you sure you want to stop the scraper?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.scraper_thread.stop()
                self.scraper_thread.terminate()
                self.scraper_thread.wait()
                self.log_message("\n⚠️ Scraping stopped by user")
                self.scraping_finished(0)
    
    def handle_error(self, error_msg):
        """Handle error messages"""
        self.log_message(f"\n❌ ERROR: {error_msg}")
        QMessageBox.critical(self, "Error", f"An error occurred:\n\n{error_msg}")
        self.scraping_finished(0)
    
    def scraping_finished(self, num_businesses):
        """Handle scraping completion"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        if num_businesses > 0:
            self.statusBar().showMessage(f"Scraping complete! {num_businesses} businesses collected.")
            QMessageBox.information(
                self, 
                "Success", 
                f"Scraping completed successfully!\n\n{num_businesses} businesses were collected and saved to your Google Sheet."
            )
        else:
            self.statusBar().showMessage("Ready")
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.scraper_thread and self.scraper_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Scraping in Progress",
                "Scraping is still running. Do you want to stop it and close?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.scraper_thread.stop()
                self.scraper_thread.terminate()
                self.scraper_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    window = ScraperGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

