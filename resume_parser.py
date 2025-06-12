import os
import re
import json
from datetime import datetime
from tkinter import filedialog, messagebox 
from rapidfuzz import fuzz  #fuzzy string matching
import shutil # file operations
import word2number # convert words to numbers

try:
    import customtkinter as ctk # CustomTkinter for modern UI
except ImportError:
    import tkinter as tk
    from tkinter import ttk
    ctk = tk
    ctk.CTk = tk.Tk
    ctk.CTkFrame = ttk.Frame
    ctk.CTkButton = ttk.Button
    ctk.CTkEntry = ttk.Entry
    ctk.CTkLabel = ttk.Label
    ctk.CTkScrollableFrame = ttk.Frame
    ctk.set_appearance_mode = lambda x: None
    ctk.set_default_color_theme = lambda x: None

try:
    import pdfplumber # PDF parsing library
except ImportError:
    class MockPDFPlumber:
        @staticmethod
        def open(file_path):
            class MockPDF:
                def __init__(self):
                    self.pages = [MockPage()]
                def __enter__(self): return self
                def __exit__(self, *args): pass
            class MockPage:
                def extract_text(self): return f"MOCK PDF TEXT from {file_path}"
            return MockPDF()
    pdfplumber = MockPDFPlumber()

class ResumeParserApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Resume Manager")
        self.geometry("1280x820")
        self.minsize(900, 600)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.resumes = []
        self.json_path = os.path.join(os.getcwd(), "resumes.json")

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=260, fg_color="#23272e")
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 8), pady=8)
        self.content = ctk.CTkScrollableFrame(self, fg_color="#181c22")
        self.content.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)

        self.statusbar = ctk.CTkLabel(self, text="Ready", anchor="w", fg_color="#23272e", height=28)
        self.statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.create_widgets()
        self.load_existing_data()

        self.skill_keywords = self.load_keywords("skills.txt", [
            "python", "java", "sql", "ai", "machine learning", "c++", "excel", "communication",
            "leadership", "accounting", "ca", "chartered accountant", "finance", "data analysis"
        ])
        self.edu_keywords = self.load_keywords("education.txt", [
            "bachelor", "master", "phd", "degree", "mba", "b.com", "bca", "mca", "ca"
        ])

    def load_keywords(self, filename, default_list):
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return [line.strip().lower() for line in f if line.strip()]
        return default_list

    def create_widgets(self):
        ctk.CTkLabel(
            self.sidebar, text="Resume Manager", font=ctk.CTkFont(size=24, weight="bold"), fg_color="transparent"
        ).pack(pady=(18, 10), padx=10)

        ctk.CTkLabel(
            self.sidebar, text="Upload and search resumes easily.", font=ctk.CTkFont(size=14), fg_color="transparent"
        ).pack(pady=(0, 18), padx=10)

        self.btn_select = ctk.CTkButton(
            self.sidebar, text="Select Resume Folder", command=self.select_folder, height=38
        )
        self.btn_select.pack(pady=(0, 18), padx=18, fill="x")

        self.search_entry = ctk.CTkEntry(
            self.sidebar, placeholder_text="Search by skill, name, etc.", height=38
        )
        self.search_entry.pack(pady=(0, 18), padx=18, fill="x")
        self.search_entry.bind("<KeyRelease>", self.perform_search)

        ctk.CTkLabel(
            self.sidebar, text="Results will appear on the right.", font=ctk.CTkFont(size=12), fg_color="transparent"
        ).pack(pady=(0, 0), padx=10)

    def set_status(self, msg):
        self.statusbar.configure(text=msg)
        self.statusbar.update_idletasks()

    def select_folder(self):
        folder_path = filedialog.askdirectory(title="Select Folder with Resumes")
        if folder_path:
            self.process_pdfs(folder_path)

    def process_pdfs(self, folder_path):
        self.set_status("Processing PDFs...")
        self.resumes = []  # Clear old resumes
        count = 0
        for filename in os.listdir(folder_path):
            if filename.lower().endswith('.pdf'):
                file_path = os.path.join(folder_path, filename)
                try:
                    resume_data = self.parse_pdf(file_path)
                    self.resumes.append(resume_data)
                    count += 1
                except Exception as e:
                    self.log_error(f"Error processing {filename}: {str(e)}")
        self.save_to_json()
        self.set_status(f"Loaded {count} resumes from selected folder.")
        self.perform_search()

    def parse_pdf(self, file_path):
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        name = self.extract_name(text, file_path)
        return {
            "file_path": os.path.abspath(file_path),  # store absolute path
            "name": name,
            "raw_text": text,
            "skills": self.extract_skills(text),
            "experience": self.extract_experience(text),
            "education": self.extract_education(text),
            "personal_info": self.extract_personal_info(text),
            "timestamp": datetime.now().isoformat()
        }

    def extract_name(self, text, file_path):
        # fallback to heuristic
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            # Heuristic: skip lines with email/phone/keywords
            for line in lines[:5]:
                if not re.search(r'@|\d|curriculum|resume|cv|bachelor|master|phd|degree', line, re.I):
                    if 2 <= len(line.split()) <= 4:
                        return line.title()
            return lines[0].title()
        return os.path.splitext(os.path.basename(file_path))[0]

    def extract_skills(self, text):
        found = set()
        for word in re.findall(r'\b\w[\w\+\#]*\b', text.lower()):
            if word in self.skill_keywords:
                found.add(word)
        return sorted(found)

    def extract_experience(self, text):
        exp_pattern = r"(\d+|\w+)[\s\-]*(years?|yrs?)"
        matches = re.findall(exp_pattern, text, re.IGNORECASE)
        total_exp = 0
        for val, _ in matches:
            try:
                if val.isdigit():
                    total_exp += int(val)
                else:
                    # Convert words like "two" to 2
                    total_exp += word2number.w2n.word_to_num(val)
            except Exception:
                continue
        return total_exp

    def extract_education(self, text):
        return [line.strip() for line in text.split('\n')
                if any(word in line.lower() for word in self.edu_keywords)]

    def extract_personal_info(self, text):
        email = re.search(r'[\w\.-]+@[\w\.-]+', text)
        phone = re.search(r'(\+?\d[\d\-\s]{8,}\d)', text)
        return {
            "email": email.group(0) if email else "",
            "phone": phone.group(0) if phone else ""
        }

    def save_to_json(self):
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.resumes, f, indent=2, ensure_ascii=False)

    def load_existing_data(self):
        if os.path.exists(self.json_path):
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.resumes = json.load(f)
        else:
            self.resumes = []
            self.save_to_json()

    def perform_search(self, event=None):
        query = self.search_entry.get().strip().lower()
        for widget in self.content.winfo_children():
            widget.destroy()

        if not query:
            # Show all resumes if search is empty
            self.display_results([(100, resume) for resume in self.resumes])
            return

        results = []
        for resume in self.resumes:
            searchable = (
                (resume.get('name', '') + " ") +
                resume['raw_text'].lower() + " " +
                " ".join(resume['skills']) + " " +
                " ".join(resume['education']) + " " +
                str(resume['experience'])
            )
            # Substring match for short queries, fuzzy for longer
            if len(query) <= 2:
                if query in searchable:
                    score = 100
                else:
                    score = 0
            else:
                score = fuzz.partial_token_sort_ratio(query, searchable)
            if score > 65:
                results.append((score, resume))

        results.sort(reverse=True, key=lambda x: x[0])
        self.display_results(results)

    def display_results(self, results):
        if not results:
            ctk.CTkLabel(
                self.content,
                text="No matching resumes found.",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color="red"
            ).pack(pady=30)
            return
        for score, resume in results:
            frame = ctk.CTkFrame(self.content, fg_color="#23272e", corner_radius=12)
            frame.pack(fill="x", pady=10, padx=10)

            # Header
            header = ctk.CTkFrame(frame, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(10, 2))

            ctk.CTkLabel(
                header,
                text=f"{resume.get('name', 'Unknown Name')}",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="#00bfff"
            ).pack(side="left", padx=(0, 12))

            ctk.CTkLabel(
                header,
                text=f"Match: {score}%",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#a0a0a0"
            ).pack(side="left", padx=(0, 12))

            ctk.CTkLabel(
                header,
                text=f"Email: {resume['personal_info'].get('email', '')}",
                font=ctk.CTkFont(size=13),
                text_color="#e0e0e0"
            ).pack(side="left", padx=(0, 12))

            ctk.CTkLabel(
                header,
                text=f"Phone: {resume['personal_info'].get('phone', '')}",
                font=ctk.CTkFont(size=13),
                text_color="#e0e0e0"
            ).pack(side="left", padx=(0, 12))

            download_btn = ctk.CTkButton(
                header,
                text="Download Resume",
                width=140,
                command=lambda path=resume['file_path']: self.download_resume(path)
            )
            download_btn.pack(side="right", padx=(0, 5))

            # Body
            body = ctk.CTkFrame(frame, fg_color="transparent")
            body.pack(fill="x", padx=10, pady=(2, 10))

            # Skills
            skills = ", ".join(resume['skills']) if resume['skills'] else "Not found"
            ctk.CTkLabel(
                body,
                text=f"Skills: {skills}",
                font=ctk.CTkFont(size=13),
                text_color="#f0e68c"
            ).pack(anchor="w", pady=(0, 2))

            # Experience
            ctk.CTkLabel(
                body,
                text=f"Experience: {resume['experience']} years",
                font=ctk.CTkFont(size=13),
                text_color="#b0e0e6"
            ).pack(anchor="w", pady=(0, 2))

            # Education
            edu_text = "Education: " + (", ".join(resume['education'][:2]) if resume['education'] else "Not found")
            ctk.CTkLabel(
                body,
                text=edu_text,
                font=ctk.CTkFont(size=13),
                text_color="#d3d3d3"
            ).pack(anchor="w", pady=(0, 2))

    def download_resume(self, file_path):
        if not os.path.isfile(file_path):
            self.set_status("Original resume file not found!")
            messagebox.showerror("Error", f"Original resume file not found:\n{file_path}")
            return
        dest_folder = filedialog.askdirectory(title="Select Destination Folder")
        if dest_folder:
            try:
                shutil.copy(file_path, dest_folder)
                self.set_status("Resume downloaded successfully!")
                messagebox.showinfo("Success", "Resume downloaded successfully!")
            except Exception as e:
                self.set_status(f"Download failed: {e}")
                messagebox.showerror("Error", f"Download failed: {e}")

    def log_error(self, msg):
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - {msg}\n")

if __name__ == "__main__":
    try:
        app = ResumeParserApp()
        app.mainloop()
    except Exception as e:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Application failed to start: {e}\n\nMake sure you've installed all required packages and activated your virtual environment.")
        root.destroy()
