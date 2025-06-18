import os
import re
import json
import pdfplumber
import csv
import customtkinter as ctk
from tkinter import filedialog
import threading
from rapidfuzz import fuzz

# Load reference data from CSVs
def load_reference_data():
    data = {
        'skills': [],
        'job_titles': [],
        'education_degrees': []
    }
    
    # Load skills
    if os.path.exists('skills.csv'):
        with open('skills.csv', 'r') as file:
            reader = csv.DictReader(file)
            data['skills'] = [row['Skill'].lower() for row in reader]
    
    # Load job titles
    if os.path.exists('job_titles.csv'):
        with open('job_titles.csv', 'r') as file:
            reader = csv.DictReader(file)
            data['job_titles'] = [row['Title'].lower() for row in reader]
    
    # Load education degrees
    if os.path.exists('education_degrees.csv'):
        with open('education_degrees.csv', 'r') as file:
            reader = csv.DictReader(file)
            data['education_degrees'] = [row['Degree'].lower() for row in reader]
    
    return data

# Parse resume text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text += extracted_text + "\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text

# Extract information using regex and reference data
def parse_resume(file_path, reference_data):
    result = {
        'name': None,
        'email': None,
        'phone': None,
        'skills': [],
        'jobs': [],
        'projects': [],
        'education': [],
        'file_path': file_path
    }
    
    # Extract text from PDF
    text = extract_text_from_pdf(file_path)
    if not text:
        return result
    
    # Store raw text
    result['raw_text'] = text
    
    # Extract email using robust regex pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    if emails:
        result['email'] = emails[0]
    
    # Extract phone using multiple patterns for different formats
    phone_patterns = [
        r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (123) 456-7890
        r'(?:\+?\d{1,3}[-.\s]?)?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # 123 456 7890
        r'(?:\+?\d{1,3}[-.\s]?)?\d{10}'  # 1234567890
    ]
    
    for pattern in phone_patterns:
        phones = re.findall(pattern, text)
        if phones:
            result['phone'] = phones[0]
            break
    
    # Extract name - look at beginning of resume
    lines = text.split('\n')
    for i in range(min(5, len(lines))):
        line = lines[i].strip()
        # Skip lines with email, phone, or address
        if '@' in line or re.search(r'\d{3}', line) or 'address' in line.lower():
            continue
        # Check if line is potential name (1-3 words, each capitalized)
        words = line.split()
        if 1 <= len(words) <= 3:
            capitalized_words = [w for w in words if len(w) > 1 and w[0].isupper()]
            if len(capitalized_words) == len(words) and len(words) >= 1:
                result['name'] = line
                break
    
    # Extract skills - comprehensive matching
    skills_found = set()
    text_lower = text.lower()
    
    # First, look for a dedicated skills section
    skills_section = None
    skills_headers = ['skills', 'technical skills', 'expertise', 'competencies', 'proficiencies', 'technologies']
    
    for header in skills_headers:
        header_pattern = re.compile(f"{header}\\s*:?", re.IGNORECASE)
        match = header_pattern.search(text)
        
        if match:
            # Find text between this header and next header
            start_pos = match.end()
            next_header_pattern = re.compile(r"\n\s*[A-Z][A-Za-z\s]+:?(?:\n|\s|$)")
            next_match = next_header_pattern.search(text, start_pos)
            
            if next_match:
                skills_section = text[start_pos:next_match.start()]
            else:
                skills_section = text[start_pos:start_pos+500]  # Limit to 500 chars
            break
    
    # Extract skills from the skills section if found
    if skills_section:
        # Split by common separators
        section_split = re.split(r'[,•\n•|/]', skills_section)
        section_items = [item.strip() for item in section_split if item.strip()]
        
        for item in section_items:
            item_lower = item.lower()
            # Check against reference skills
            for skill in reference_data['skills']:
                if skill in item_lower:
                    skills_found.add(skill.capitalize())
    
    # Look for skills throughout the document
    for skill in reference_data['skills']:
        if skill.lower() in text_lower:
            skills_found.add(skill.capitalize())
    
    result['skills'] = sorted(list(skills_found))
    
    # Extract education - look for degree mentions
    education_found = []
    
    for degree in reference_data['education_degrees']:
        if degree.lower() in text_lower:
            # Find the context around this degree
            degree_pattern = re.compile(f"{re.escape(degree)}\\b", re.IGNORECASE)
            match = degree_pattern.search(text)
            if match:
                # Extract context around the degree
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end].strip()
                
                # university/institution name
                university_patterns = ['university', 'college', 'institute', 'school']
                university = None
                
                for uni_pattern in university_patterns:
                    uni_match = re.search(f"\\b{uni_pattern}\\s+of\\s+[A-Z][a-zA-Z\\s]+\\b", context, re.IGNORECASE)
                    if uni_match:
                        university = uni_match.group(0)
                        break
                
                if not university:
                    # Word starting with capital followed by University
                    for uni_pattern in university_patterns:
                        uni_match = re.search(f"\\b[A-Z][a-zA-Z\\s]+\\s+{uni_pattern}\\b", context, re.IGNORECASE)
                        if uni_match:
                            university = uni_match.group(0)
                            break
                
                # Look for graduation year
                year_match = re.search(r'\b(19|20)\d{2}\b', context)
                year = year_match.group(0) if year_match else None
                
                education_found.append({
                    'degree': degree,
                    'institution': university if university else "Institution name not found",
                    'year': year,
                    'context': context
                })
    
    result['education'] = education_found
    
    # Extract work experience - look for job titles
    jobs_found = []
    
    for title in reference_data['job_titles']:
        if title.lower() in text_lower:
            title_pattern = re.compile(f"{re.escape(title)}\\b", re.IGNORECASE)
            
            for match in title_pattern.finditer(text):
                start = max(0, match.start() - 150)
                end = min(len(text), match.end() + 150)
                context = text[start:end].strip()
                
                # Look for company name and dates
                company = None
                date = None
                
                # Check for date patterns in context
                date_patterns = [
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s+[-–—]\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|Present',
                    r'\d{4}\s+[-–—]\s+\d{4}',
                    r'\d{4}\s+[-–—]\s+Present'
                ]
                
                for date_pattern in date_patterns:
                    date_match = re.search(date_pattern, context, re.IGNORECASE)
                    if date_match:
                        date = date_match.group(0)
                        break
                
                # Look for possible company name
                company_indicators = ['at', 'with', 'for', '-', '|', ',']
                for indicator in company_indicators:
                    company_pattern = f"{re.escape(title)}\\s*{re.escape(indicator)}\\s*([A-Z][A-Za-z0-9\\s&.,]+)"
                    company_match = re.search(company_pattern, context, re.IGNORECASE)
                    if company_match:
                        company = company_match.group(1).strip()
                        break
                
                if not company:
                    # Company followed by job title
                    for indicator in company_indicators:
                        company_pattern = f"([A-Z][A-Za-z0-9\\s&.,]+)\\s*{re.escape(indicator)}\\s*{re.escape(title)}"
                        company_match = re.search(company_pattern, context, re.IGNORECASE)
                        if company_match:
                            company = company_match.group(1).strip()
                            break
                
                # responsibilities/achievements (bullet points)
                responsibilities = []
                bullet_pattern = r'[•\-\*]\s*([^\n•\-\*]+)'
                bullet_matches = re.findall(bullet_pattern, context)
                responsibilities = [match.strip() for match in bullet_matches if len(match.strip()) > 10]
                
                jobs_found.append({
                    'title': title,
                    'company': company if company else "Company name not found",
                    'date': date if date else "Date not found",
                    'responsibilities': responsibilities[:3],  # Keep only first 3 responsibilities
                    'context': context
                })
    
    result['jobs'] = jobs_found
    
    # Extract projects - look for project indicators
    projects_found = []
    project_headers = ['projects', 'key projects', 'professional projects', 'portfolio', 'project work']
    
    for header in project_headers:
        header_pattern = re.compile(f"{header}\\s*:?", re.IGNORECASE)
        match = header_pattern.search(text)
        
        if match:
            # Find text btw this header and next header
            start_pos = match.end()
            next_header_pattern = re.compile(r"\n\s*[A-Z][A-Za-z\s]+:?(?:\n|\s|$)")
            next_match = next_header_pattern.search(text, start_pos)
            
            if next_match:
                projects_section = text[start_pos:next_match.start()]
            else:
                projects_section = text[start_pos:start_pos+800]  # Limit to 800 chars
            
            # Split the projects section and process
            lines = projects_section.split('\n')
            current_project = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if this is a new project (often starts with a title)
                if not line.startswith('•') and not line.startswith('-') and len(line) < 100:
                    if current_project:
                        projects_found.append(current_project)
                    
                    current_project = {
                        'title': line,
                        'description': []
                    }
                elif current_project:
                    # This line is part of the current project description
                    current_project['description'].append(line)
            
            # Add the last project
            if current_project:
                projects_found.append(current_project)
            
            break
    
    # Limit project descriptions to 3 lines each
    for project in projects_found:
        if 'description' in project:
            project['description'] = project['description'][:3]
    
    result['projects'] = projects_found
    
    return result

# Define the main application class
class ResumeParserApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("Advanced Resume Matcher")
        self.geometry("1200x800")
        
        # Set appearance mode and color theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        # Configure grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Initialize data
        self.resumes = []
        self.reference_data = load_reference_data()
        self.json_path = os.path.join(os.getcwd(), "parsed_resumes.json")
        
        # Create sidebar
        self.create_sidebar()
        
        # Create main content area
        self.create_main_content()
        
        # Load existing data if available
        self.load_existing_data()
        
        # Status variables
        self.parsing_in_progress = False
    
    def create_sidebar(self):
        # Create sidebar frame
        self.sidebar = ctk.CTkFrame(self, width=280)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # App title
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="Resume Matcher Pro",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.pack(pady=(20, 10))
        
        self.subtitle_label = ctk.CTkLabel(
            self.sidebar,
            text="Advanced Resume Analysis Tool",
            font=ctk.CTkFont(size=12)
        )
        self.subtitle_label.pack(pady=(0, 20))
        
        # Add file button
        self.btn_add_file = ctk.CTkButton(
            self.sidebar,
            text="📄 Add Resume File",
            command=self.select_file,
            height=40
        )
        self.btn_add_file.pack(pady=10, padx=20, fill="x")
        
        # Add folder button
        self.btn_add_folder = ctk.CTkButton(
            self.sidebar,
            text="📁 Add Resume Folder",
            command=self.select_folder,
            height=40
        )
        self.btn_add_folder.pack(pady=10, padx=20, fill="x")
        
        # Clear all button
        self.btn_clear = ctk.CTkButton(
            self.sidebar,
            text="🗑️ Clear All",
            command=self.clear_all,
            height=40,
            fg_color="red"
        )
        self.btn_clear.pack(pady=10, padx=20, fill="x")
        
        # Search entry
        self.search_label = ctk.CTkLabel(
            self.sidebar,
            text="Search Resumes:",
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.search_label.pack(pady=(20, 5), padx=20, fill="x")
        
        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="Search by skills, experience, name...",
            height=40
        )
        self.search_entry.pack(pady=10, padx=20, fill="x")
        self.search_entry.bind("<KeyRelease>", self.perform_search)
        
        # Quick filter buttons
        self.filter_label = ctk.CTkLabel(
            self.sidebar,
            text="Quick Filters:",
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.filter_label.pack(pady=(20, 5), padx=20, fill="x")
        
        self.btn_filter_python = ctk.CTkButton(
            self.sidebar,
            text="Python",
            command=lambda: self.quick_filter("python"),
            height=30
        )
        self.btn_filter_python.pack(pady=2, padx=20, fill="x")
        
        self.btn_filter_java = ctk.CTkButton(
            self.sidebar,
            text="Java",
            command=lambda: self.quick_filter("java"),
            height=30
        )
        self.btn_filter_java.pack(pady=2, padx=20, fill="x")
        
        self.btn_filter_manager = ctk.CTkButton(
            self.sidebar,
            text="Manager",
            command=lambda: self.quick_filter("manager"),
            height=30
        )
        self.btn_filter_manager.pack(pady=2, padx=20, fill="x")
        
        # Status frame
        self.status_frame = ctk.CTkFrame(self.sidebar)
        self.status_frame.pack(pady=(20, 10), padx=20, fill="x")
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Ready",
            anchor="w"
        )
        self.status_label.pack(pady=10, padx=10, fill="x")
        
        # Count label
        self.count_label = ctk.CTkLabel(
            self.status_frame,
            text="Resumes: 0",
            anchor="w",
            font=ctk.CTkFont(weight="bold")
        )
        self.count_label.pack(pady=(0, 10), padx=10, fill="x")
    
    def create_main_content(self):
        # Create scrollable frame for content
        self.content = ctk.CTkScrollableFrame(self)
        self.content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Welcome message
        self.welcome_label = ctk.CTkLabel(
            self.content,
            text="Welcome to Advanced Resume Matcher!",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.welcome_label.pack(pady=20)
        
        self.instruction_label = ctk.CTkLabel(
            self.content,
            text="Select a resume file or folder to begin parsing.\nThis tool extracts names, emails, phones, skills, experience, projects, and education.",
            font=ctk.CTkFont(size=14)
        )
        self.instruction_label.pack(pady=10)
        
        # Features list
        features_frame = ctk.CTkFrame(self.content)
        features_frame.pack(pady=20, padx=20, fill="x")
        
        features_title = ctk.CTkLabel(
            features_frame,
            text="Features:",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        features_title.pack(pady=10)
        
        features = [
            " - Extracts names, emails, and phone numbers",
            " - Identifies technical skills and competencies",
            " - Parses work experience and job history",
            " - Extracts education and qualifications",
            " - Identifies projects and achievements",
            " - Supports multiple resume formats",
            " - Real-time search and filtering",
            " - JSON export for easy integration"
        ]
        
        for feature in features:
            feature_label = ctk.CTkLabel(
                features_frame,
                text=feature,
                anchor="w"
            )
            feature_label.pack(pady=2, padx=20, fill="x")
    
    def quick_filter(self, term):
        self.search_entry.delete(0, 'end')
        self.search_entry.insert(0, term)
        self.perform_search()
    
    def clear_all(self):
        # Clear all resumes
        self.resumes = []
        self.save_to_json()
        self.count_label.configure(text="Resumes: 0")
        self.status_label.configure(text="All resumes cleared")
        
        # Clear display
        for widget in self.content.winfo_children():
            widget.destroy()
        self.create_main_content()
    
    def select_file(self):
        if self.parsing_in_progress:
            return
        
        file_path = filedialog.askopenfilename(
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        
        if file_path:
            self.process_file(file_path)
    
    def select_folder(self):
        if self.parsing_in_progress:
            return
        
        folder_path = filedialog.askdirectory()
        
        if folder_path:
            self.process_folder(folder_path)
    
    def process_file(self, file_path):
        self.parsing_in_progress = True
        self.status_label.configure(text=f"Parsing {os.path.basename(file_path)}...")
        self.update_idletasks()
        
        # Start parsing in a separate thread
        threading.Thread(target=self._parse_file_thread, args=(file_path,)).start()
    
    def _parse_file_thread(self, file_path):
        try:
            # Parse the file
            result = parse_resume(file_path, self.reference_data)
            
            # Add to resumes list if not already present
            file_exists = False
            for resume in self.resumes:
                if resume['file_path'] == file_path:
                    file_exists = True
                    break
            
            if not file_exists:
                self.resumes.append(result)
                
                # Save to JSON
                self.save_to_json()
                
                # Update status and counts
                self.status_label.configure(text=f"Successfully parsed {os.path.basename(file_path)}")
                self.count_label.configure(text=f"Resumes: {len(self.resumes)}")
                
                # Refresh display
                self.display_results([result])
        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}")
        finally:
            self.parsing_in_progress = False
    
    def process_folder(self, folder_path):
        self.parsing_in_progress = True
        
        # Find PDF files in the folder
        pdf_files = []
        for filename in os.listdir(folder_path):
            if filename.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(folder_path, filename))
        
        if not pdf_files:
            self.status_label.configure(text="No PDF files found in folder")
            self.parsing_in_progress = False
            return
        
        self.status_label.configure(text=f"Found {len(pdf_files)} PDF files. Processing...")
        self.update_idletasks()
        
        # Start parsing in a separate thread
        threading.Thread(target=self._parse_folder_thread, args=(pdf_files,)).start()
    
    def _parse_folder_thread(self, pdf_files):
        try:
            results = []
            for i, file_path in enumerate(pdf_files):
                # Update status for each file
                self.status_label.configure(text=f"Parsing file {i+1}/{len(pdf_files)}: {os.path.basename(file_path)}")
                self.update_idletasks()
                
                # Parse the file
                result = parse_resume(file_path, self.reference_data)
                
                # Add to resumes list if not already present
                file_exists = False
                for resume in self.resumes:
                    if resume['file_path'] == file_path:
                        file_exists = True
                        break
                
                if not file_exists:
                    self.resumes.append(result)
                    results.append(result)
            
            # Save to JSON
            self.save_to_json()
            
            # Update status and counts
            self.status_label.configure(text=f"Successfully parsed {len(results)} new resumes")
            self.count_label.configure(text=f"Resumes: {len(self.resumes)}")
            
            # Refresh display
            self.display_results(results)
        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}")
        finally:
            self.parsing_in_progress = False
    
    def save_to_json(self):
        try:
            with open(self.json_path, 'w') as f:
                # Create a simplified version for storage
                simplified_resumes = []
                for resume in self.resumes:
                    # Don't store raw text in the JSON file
                    resume_copy = resume.copy()
                    if 'raw_text' in resume_copy:
                        del resume_copy['raw_text']
                    simplified_resumes.append(resume_copy)
                
                json.dump(simplified_resumes, f, indent=2)
        except Exception as e:
            print(f"Error saving to JSON: {e}")
    
    def load_existing_data(self):
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r') as f:
                    self.resumes = json.load(f)
                    self.count_label.configure(text=f"Resumes: {len(self.resumes)}")
                    if self.resumes:
                        self.status_label.configure(text=f"Loaded {len(self.resumes)} existing resumes")
            except Exception as e:
                print(f"Error loading JSON: {e}")
    
    def perform_search(self, event=None):
        query = self.search_entry.get().lower().strip()
        
        if not query:
            # Clear results if search is empty
            for widget in self.content.winfo_children():
                widget.destroy()
            self.create_main_content()
            return
        
        # Find matching resumes
        results = []
        for resume in self.resumes:
            # Create searchable text from resume data
            search_text = ""
            if resume.get('name'):
                search_text += resume['name'] + " "
            if resume.get('email'):
                search_text += resume['email'] + " "
            if resume.get('skills'):
                search_text += " ".join(resume['skills']) + " "
            
            # Add job information
            for job in resume.get('jobs', []):
                if isinstance(job, dict):
                    for key, value in job.items():
                        if key != 'context' and value:  # Skip context field
                            if isinstance(value, list):
                                search_text += " ".join(value) + " "
                            else:
                                search_text += str(value) + " "
            
            # Add education information
            for edu in resume.get('education', []):
                if isinstance(edu, dict):
                    for key, value in edu.items():
                        if key != 'context' and value:
                            search_text += str(value) + " "
            
            # Add project information
            for project in resume.get('projects', []):
                if isinstance(project, dict):
                    for key, value in project.items():
                        if key != 'context' and value:
                            if isinstance(value, list):
                                search_text += " ".join(value) + " "
                            else:
                                search_text += str(value) + " "
            
            # Calculate match score
            search_text = search_text.lower()
            
            # Direct match gets highest score
            if query in search_text:
                score = 100
            else:
                # Fuzzy match for partial matches
                score = fuzz.partial_ratio(query, search_text)
            
            if score > 60:  # Threshold for including in results
                results.append((score, resume))
        
        # Sort by score (highest first)
        results.sort(reverse=True, key=lambda x: x[0])
        
        # Display results
        self.display_results([r[1] for r in results])
    
    def display_results(self, results):
        # Clear previous results
        for widget in self.content.winfo_children():
            widget.destroy()
        
        if not results:
            # Show no results message
            no_results_label = ctk.CTkLabel(
                self.content,
                text="No matching resumes found",
                font=ctk.CTkFont(size=16)
            )
            no_results_label.pack(pady=20)
            return
        
        # Show results count
        results_count_label = ctk.CTkLabel(
            self.content,
            text=f"Found {len(results)} matching resume(s)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        results_count_label.pack(pady=10)
        
        # Display each result
        for resume in results:
            self.create_result_card(resume)
    
    def create_result_card(self, resume):
        # Create a card for the resume
        card = ctk.CTkFrame(self.content)
        card.pack(fill="x", pady=10, padx=10)
        
        # Header with name and contact info
        header = ctk.CTkFrame(card, fg_color=("#3B8ED0", "#1F6AA5"))
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        # Name (if available)
        if resume.get('name'):
            name_label = ctk.CTkLabel(
                header,
                text=resume['name'],
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="white"
            )
            name_label.pack(anchor="w", padx=10, pady=(10, 5))
        else:
            name_label = ctk.CTkLabel(
                header,
                text=os.path.basename(resume['file_path']),
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="white"
            )
            name_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # Contact info (if available)
        contact_info = []
        if resume.get('email'):
            contact_info.append(f"📧 {resume['email']}")
        if resume.get('phone'):
            contact_info.append(f"📞 {resume['phone']}")
        
        if contact_info:
            contact_label = ctk.CTkLabel(
                header,
                text=" | ".join(contact_info),
                font=ctk.CTkFont(size=12),
                text_color="white"
            )
            contact_label.pack(anchor="w", padx=10, pady=(0, 10))
        
        # Skills section
        if resume.get('skills'):
            skills_frame = ctk.CTkFrame(card, fg_color="transparent")
            skills_frame.pack(fill="x", padx=15, pady=5)
            
            skills_header = ctk.CTkLabel(
                skills_frame,
                text="💼 Skills:",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            skills_header.pack(anchor="w")
            
            # Create a frame for skill chips
            skills_chips = ctk.CTkFrame(skills_frame, fg_color="transparent")
            skills_chips.pack(fill="x", pady=5)
            
            # Add skill chips
            row_frame = ctk.CTkFrame(skills_chips, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            
            for i, skill in enumerate(resume['skills'][:15]):  # Limit to 15 skills
                # Create a new row every 5 skills
                if i > 0 and i % 5 == 0:
                    row_frame = ctk.CTkFrame(skills_chips, fg_color="transparent")
                    row_frame.pack(fill="x", pady=2)
                
                skill_chip = ctk.CTkLabel(
                    row_frame,
                    text=skill,
                    fg_color=("#2B2B2B", "#3D3D3D"),
                    corner_radius=10,
                    padx=10,
                    pady=5
                )
                skill_chip.pack(side="left", padx=3)
            
            # Show more skills count if there are many
            if len(resume['skills']) > 15:
                more_skills_label = ctk.CTkLabel(
                    skills_chips,
                    text=f"... and {len(resume['skills']) - 15} more",
                    font=ctk.CTkFont(size=10, slant="italic")
                )
                more_skills_label.pack(anchor="w", pady=5)
        
        # Work exp section
        if resume.get('jobs'):
            jobs_frame = ctk.CTkFrame(card, fg_color="transparent")
            jobs_frame.pack(fill="x", padx=15, pady=5)
            
            jobs_header = ctk.CTkLabel(
                jobs_frame,
                text="💼 Work Experience:",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            jobs_header.pack(anchor="w")
            
            # Add job details 
            for job in resume['jobs'][:3]:
                job_frame = ctk.CTkFrame(jobs_frame, fg_color=("#F0F0F0", "#2B2B2B"))
                job_frame.pack(fill="x", pady=5)
                
                # Job title
                if 'title' in job:
                    title_label = ctk.CTkLabel(
                        job_frame,
                        text=job['title'],
                        font=ctk.CTkFont(size=12, weight="bold")
                    )
                    title_label.pack(anchor="w", padx=10, pady=(10, 2))
                
                # Company and date
                company_date = []
                if 'company' in job and job['company'] != "Company name not found":
                    company_date.append(job['company'])
                if 'date' in job and job['date'] != "Date not found":
                    company_date.append(job['date'])
                
                if company_date:
                    company_label = ctk.CTkLabel(
                        job_frame,
                        text=" | ".join(company_date),
                        font=ctk.CTkFont(size=11)
                    )
                    company_label.pack(anchor="w", padx=10, pady=(0, 5))
                
                # Responsibilities
                if 'responsibilities' in job and job['responsibilities']:
                    for resp in job['responsibilities'][:2]:  # Show only first 2 responsibilities
                        resp_label = ctk.CTkLabel(
                            job_frame,
                            text=f"• {resp}",
                            font=ctk.CTkFont(size=10),
                            justify="left"
                        )
                        resp_label.pack(anchor="w", padx=20, pady=1)
                
                # Add padding at bottom
                ctk.CTkLabel(job_frame, text="", height=5).pack()
            
            # Show count if there are more jobs
            if len(resume['jobs']) > 3:
                more_jobs_label = ctk.CTkLabel(
                    jobs_frame,
                    text=f"... and {len(resume['jobs']) - 3} more positions",
                    font=ctk.CTkFont(size=10, slant="italic")
                )
                more_jobs_label.pack(anchor="w", pady=5)
        
        # Education section
        if resume.get('education'):
            education_frame = ctk.CTkFrame(card, fg_color="transparent")
            education_frame.pack(fill="x", padx=15, pady=5)
            
            education_header = ctk.CTkLabel(
                education_frame,
                text="🎓 Education:",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            education_header.pack(anchor="w")
            
            # Add education details
            for edu in resume['education'][:2]:  # Limit to 2 education entries
                edu_frame = ctk.CTkFrame(education_frame, fg_color=("#F0F0F0", "#2B2B2B"))
                edu_frame.pack(fill="x", pady=5)
                
                # Degree
                if 'degree' in edu:
                    degree_label = ctk.CTkLabel(
                        edu_frame,
                        text=edu['degree'],
                        font=ctk.CTkFont(size=12, weight="bold")
                    )
                    degree_label.pack(anchor="w", padx=10, pady=(10, 2))
                
                # Institution and year
                inst_year = []
                if 'institution' in edu and edu['institution'] != "Institution name not found":
                    inst_year.append(edu['institution'])
                if 'year' in edu and edu['year']:
                    inst_year.append(edu['year'])
                
                if inst_year:
                    institution_label = ctk.CTkLabel(
                        edu_frame,
                        text=" | ".join(inst_year),
                        font=ctk.CTkFont(size=11)
                    )
                    institution_label.pack(anchor="w", padx=10, pady=(0, 10))
        
        # Projects section
        if resume.get('projects'):
            projects_frame = ctk.CTkFrame(card, fg_color="transparent")
            projects_frame.pack(fill="x", padx=15, pady=5)
            
            projects_header = ctk.CTkLabel(
                projects_frame,
                text="🚀 Projects:",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            projects_header.pack(anchor="w")
            
            # Add project details
            for project in resume['projects'][:2]:  # Limit to 2 projects
                project_frame = ctk.CTkFrame(projects_frame, fg_color=("#F0F0F0", "#2B2B2B"))
                project_frame.pack(fill="x", pady=5)
                
                # Project title
                if 'title' in project:
                    title_label = ctk.CTkLabel(
                        project_frame,
                        text=project['title'],
                        font=ctk.CTkFont(size=12, weight="bold")
                    )
                    title_label.pack(anchor="w", padx=10, pady=(10, 5))
                
                # Description
                if 'description' in project and project['description']:
                    for desc in project['description'][:1]:  # Show only first description line
                        desc_label = ctk.CTkLabel(
                            project_frame,
                            text=f"• {desc}",
                            font=ctk.CTkFont(size=10),
                            justify="left"
                        )
                        desc_label.pack(anchor="w", padx=20, pady=1)
                
                # Add padding at bottom
                ctk.CTkLabel(project_frame, text="", height=5).pack()
            
            # Show count if there are more projects
            if len(resume['projects']) > 2:
                more_projects_label = ctk.CTkLabel(
                    projects_frame,
                    text=f"... and {len(resume['projects']) - 2} more projects",
                    font=ctk.CTkFont(size=10, slant="italic")
                )
                more_projects_label.pack(anchor="w", pady=5)
        
        # File path at the bottom
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=15, pady=(5, 10))
        
        file_label = ctk.CTkLabel(
            footer,
            text=f"📁 File: {os.path.basename(resume['file_path'])}",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        file_label.pack(anchor="w")

# Main execution
if __name__ == "__main__":
    # First, create the reference data files if they don't exist
    if not os.path.exists('skills.csv') or not os.path.exists('job_titles.csv') or not os.path.exists('education_degrees.csv'):
        print("Creating reference data files...")
        
        # Create skills CSV
        skills = [
            # Programming Languages
            "Python", "Java", "C++", "C#", "JavaScript", "TypeScript", "PHP", "Ruby", "Go", "Swift",
            "Kotlin", "Scala", "R", "MATLAB", "Perl", "Rust", "Objective-C", "VBA", "Shell Scripting", "PowerShell",
            "Bash", "HTML", "CSS", "SQL", "NoSQL", "Assembly", "Dart", "Lua", "Groovy", "Haskell",
            
            # Frameworks & Libraries
            "React", "Angular", "Vue.js", "Django", "Flask", "Spring", "ASP.NET", "Express.js", "Node.js", "jQuery",
            "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Pandas", "NumPy", "Matplotlib", "Seaborn", "D3.js", "Bootstrap",
            "Tailwind CSS", "Laravel", "Ruby on Rails", "Symfony", "FastAPI", "Redux", "Next.js", "Gatsby", "Svelte", "Flutter",
            
            # Databases
            "MySQL", "PostgreSQL", "MongoDB", "SQLite", "Oracle", "Microsoft SQL Server", "Redis", "Cassandra", "DynamoDB", "Elasticsearch",
            "Firebase", "MariaDB", "Neo4j", "CouchDB", "Firestore", "Amazon RDS", "Azure SQL", "Cosmos DB", "IBM Db2", "Snowflake",
            
            # Cloud Services
            "AWS", "Azure", "Google Cloud Platform", "IBM Cloud", "Oracle Cloud", "DigitalOcean", "Heroku", "Alibaba Cloud", "Linode", "Vultr",
            "AWS Lambda", "Amazon S3", "EC2", "Azure Functions", "Google Kubernetes Engine", "AWS ECS", "Cloud Foundry", "Azure DevOps", "AWS CodePipeline", "Google App Engine",
            
            # DevOps & Tools
            "Docker", "Kubernetes", "Jenkins", "Git", "GitHub", "GitLab", "Bitbucket", "Travis CI", "CircleCI", "Ansible",
            "Terraform", "Puppet", "Chef", "Vagrant", "Jira", "Confluence", "Trello", "Slack", "Microsoft Teams", "Notion"
        ]
        
        with open('skills.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Skill'])
            for skill in skills:
                writer.writerow([skill])
        
        # Create job titles CSV
        job_titles = [
            "Software Engineer", "Senior Software Engineer", "Software Developer", "Full Stack Developer", "Frontend Developer", 
            "Backend Developer", "Mobile Developer", "iOS Developer", "Android Developer", "Web Developer",
            "DevOps Engineer", "Site Reliability Engineer", "Platform Engineer", "QA Engineer", "Test Automation Engineer",
            "Systems Architect", "Solutions Architect", "Technical Architect", "Cloud Architect", "Software Architect",
            "Data Scientist", "Data Analyst", "Business Intelligence Analyst", "Business Analyst", "Data Engineer",
            "Machine Learning Engineer", "AI Research Scientist", "Quantitative Analyst", "Statistical Analyst", "Big Data Engineer",
            "Project Manager", "Product Manager", "Program Manager", "Scrum Master", "Agile Coach",
            "Engineering Manager", "Technical Lead", "Team Lead", "CTO", "CIO"
        ]
        
        with open('job_titles.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Title'])
            for title in job_titles:
                writer.writerow([title])
        
        # Create education degrees CSV
        degrees = [
            "Bachelor of Science (BS)", "Bachelor of Arts (BA)", "Bachelor of Engineering (BE)", 
            "Bachelor of Technology (BTech)", "Bachelor of Computer Science", "Bachelor of Computer Applications (BCA)",
            "Master of Science (MS)", "Master of Arts (MA)", "Master of Engineering (ME)",
            "Master of Technology (MTech)", "Master of Computer Applications (MCA)", "Master of Business Administration (MBA)",
            "Doctor of Philosophy (PhD)", "Doctor of Engineering (DEng)", "Doctor of Science (DSc)",
            "Associate of Science (AS)", "Associate of Arts (AA)", "Diploma in Computer Science"
        ]
        
        with open('education_degrees.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Degree'])
            for degree in degrees:
                writer.writerow([degree])
        
        print("Reference data files created successfully!")
    
    # Create and run the application
    app = ResumeParserApp()
    app.mainloop()
