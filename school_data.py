import sqlite3, os, time, pyinputplus as pyip

connection = sqlite3.connect("schooldata.db")
cursor = connection.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS Students 
               (StudentID INTEGER PRIMARY KEY AUTOINCREMENT,Firstname TEXT, 
               Surname TEXT, DOB DATE, Gender TEXT, Mastery TEXT,
               Yeargroup INTEGER,  Email TEXT, Subject1 INTEGER ALLOW NULL, Subject2 INTEGER ALLOW NULL, 
               Subject3 INTEGER ALLOW NULL, Subject4 INTEGER ALLOW NULL,
               FOREIGN KEY(Subject1) REFERENCES Subjects(SubjectID),
               FOREIGN KEY(Subject2) REFERENCES Subjects(SubjectID),
               FOREIGN KEY(Subject3) REFERENCES Subjects(SubjectID),
               FOREIGN KEY(Subject4) REFERENCES Subjects(SubjectID))''')


cursor.execute('''CREATE TABLE IF NOT EXISTS Timetable 
               ( StudentID INTEGER NOT NULL, Day INTEGER, Period1 INTEGER, Period2 INTEGER, 
                Period3 INTEGER, Period4 INTEGER, Period5 INTEGER, Period6 INTEGER,
                Period7 INTEGER, Period8 INTEGER, 
                FOREIGN KEY(StudentID) REFERENCES Students(StudentID), 
                FOREIGN KEY(Period1) REFERENCES Mastery(MasteryID),
                FOREIGN KEY(Period2) REFERENCES Subjects(SubjectID),
                FOREIGN KEY(Period3) REFERENCES Subjects(SubjectID),
                FOREIGN KEY(Period4) REFERENCES Subjects(SubjectID),
                FOREIGN KEY(Period5) REFERENCES Mastery(MasteryID),
                FOREIGN KEY(Period6) REFERENCES Subjects(SubjectID),
                FOREIGN KEY(Period7) REFERENCES Subjects(SubjectID),
                FOREIGN KEY(Period8) REFERENCES Subjects(SubjectID),
                UNIQUE(StudentID, Day))''')


cursor.execute('''CREATE TABLE IF NOT EXISTS Student_Info 
               (StudentID INTEGER, Parentname TEXT, Parentnumber INTEGER, 
               Address TEXT, Nationality TEXT, countryofbirth TEXT, Enrollmentdate DATE, 
               FOREIGN KEY(StudentID) REFERENCES Students(StudentID))''') 


cursor.execute('''CREATE TABLE IF NOT EXISTS Medical_Info 
               (StudentID INTEGER, Conditions TEXT, Medication TEXT, Allergies TEXT, 
               Needs TEXT, FOREIGN KEY(StudentID) REFERENCES Students(StudentID))''')


cursor.execute('''CREATE TABLE IF NOT EXISTS Mastery
                (MasteryID INTEGER PRIMARY KEY AUTOINCREMENT, Masteryname TEXT, Yeargroup INTEGER)''')


cursor.execute('''CREATE TABLE IF NOT EXISTS Attendance 
               (AttendanceID INTEGER PRIMARY KEY AUTOINCREMENT, StudentID INTEGER, 
               Date DATE, Status TEXT, FOREIGN KEY(StudentID) REFERENCES Students(StudentID))''')


cursor.execute('''CREATE TABLE IF NOT EXISTS PeriodAttendance 
               (PeriodAttendanceID INTEGER PRIMARY KEY AUTOINCREMENT, StudentID INTEGER, 
               Date DATE, Period INTEGER, TeacherID INTEGER, Status TEXT,
               FOREIGN KEY(StudentID) REFERENCES Students(StudentID),
               FOREIGN KEY(TeacherID) REFERENCES Teachers(TeacherID),
               UNIQUE(StudentID, Date, Period))''')



cursor.execute('''CREATE TABLE IF NOT EXISTS BehaviourEvents
               (BehaviourID INTEGER PRIMARY KEY AUTOINCREMENT, StudentID INTEGER, 
               Date DATE, Period INTEGER, TypeID INTEGER, Description TEXT,
               FOREIGN KEY(TypeID) REFERENCES BehaviourTypes(TypeID),
               FOREIGN KEY(StudentID) REFERENCES Students(StudentID))''')



cursor.execute('''CREATE TABLE IF NOT EXISTS BehaviourTypes 
               (TypeID INTEGER PRIMARY KEY AUTOINCREMENT, Type TEXT)''')



cursor.execute('''CREATE TABLE IF NOT EXISTS Teachers 
               (TeacherID INTEGER PRIMARY KEY AUTOINCREMENT, Firstname TEXT, 
                Surname TEXT, Gender TEXT, Email TEXT, Role TEXT, SubjectID INTEGER, 
                MasteryID INTEGER, 
                FOREIGN KEY(MasteryID) REFERENCES Mastery(MasteryID),
                FOREIGN KEY(SubjectID) REFERENCES Subjects(SubjectID))''')


cursor.execute('''CREATE TABLE IF NOT EXISTS Teacher_info 
               (TeacherID INTEGER, phonenumber INTEGER, personal_email TEXT, DOB DATE,
                qualifications TEXT, Emergency_contact INTEGER, Address TEXT,
                employment_start DATE,
                FOREIGN KEY(TeacherID) REFERENCES Teachers(TeacherID))''')


cursor.execute('''CREATE TABLE IF NOT EXISTS Subjects 
                (SubjectID INTEGER PRIMARY KEY AUTOINCREMENT, Subjectname TEXT)''')


cursor.execute('''CREATE TABLE IF NOT EXISTS Scores 
               (ScoreID INTEGER PRIMARY KEY AUTOINCREMENT, StudentID INTEGER, SubjectID INTEGER, 
               Score INTEGER, Assessment1 INTEGER, Assessment2 INTEGER, Assessment3 INTEGER, 
               FOREIGN KEY(StudentID) REFERENCES Students(StudentID), 
               FOREIGN KEY(Assessment1) REFERENCES Assessments(AssessmentID),
               FOREIGN KEY(Assessment2) REFERENCES Assessments(AssessmentID),
               FOREIGN KEY(Assessment3) REFERENCES Assessments(AssessmentID),
               FOREIGN KEY(SubjectID) REFERENCES Subjects(SubjectID))''')   


cursor.execute('''CREATE TABLE IF NOT EXISTS Assessments
               (AssessmentID INTEGER PRIMARY KEY AUTOINCREMENT, StudentID INTEGER, 
               SubjectID INTEGER, Type TEXT, Score FLOAT, Date DATE, 
               FOREIGN KEY(StudentID) REFERENCES Students(StudentID), 
               FOREIGN KEY(SubjectID) REFERENCES Subjects(SubjectID))''')


cursor.execute('''CREATE TABLE IF NOT EXISTS Summaries
               (SummaryID INTEGER PRIMARY KEY AUTOINCREMENT, StudentID INTEGER, 
               Week DATE, SummaryText TEXT, 
               FOREIGN KEY(StudentID) REFERENCES Students(StudentID))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS Posts 
               (PostID INTEGER PRIMARY KEY AUTOINCREMENT,Title TEXT, Content TEXT, 
               Date DATE, Time Text, Attachments MEDIUMBLOB, Comments TEXT, TeacherID INTEGER,
               FOREIGN KEY(TeacherID) REFERENCES Teachers(TeacherID))''')


cursor.execute('''CREATE TABLE IF NOT EXISTS M_Posts 
               (MPostID INTEGER PRIMARY KEY AUTOINCREMENT,Title TEXT, Content TEXT, 
               Date DATE, Time Text, Attachments MEDIUMBLOB, Comments TEXT, TeacherID INTEGER,
               FOREIGN KEY(TeacherID) REFERENCES Teachers(TeacherID))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS E_Posts 
               (EPostID INTEGER PRIMARY KEY AUTOINCREMENT,Title TEXT, Content TEXT, 
               Date DATE, Time Text, Attachments MEDIUMBLOB, TeacherID INTEGER,
               FOREIGN KEY(TeacherID) REFERENCES Teachers(TeacherID))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS S_Posts 
               (SPostID INTEGER PRIMARY KEY AUTOINCREMENT,Title TEXT, Content TEXT, 
               Date DATE, Time Text, Attachments MEDIUMBLOB, TeacherID INTEGER,
               FOREIGN KEY(TeacherID) REFERENCES Teachers(TeacherID))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS C_Posts 
               (CPostID INTEGER PRIMARY KEY AUTOINCREMENT,Title TEXT, Content TEXT, 
               Date DATE, Time Text, Attachments MEDIUMBLOB, TeacherID INTEGER,
               FOREIGN KEY(TeacherID) REFERENCES Teachers(TeacherID))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS H_Posts 
               (HPostID INTEGER PRIMARY KEY AUTOINCREMENT,Title TEXT, Content TEXT, 
               Date DATE, Time Text, Attachments MEDIUMBLOB, TeacherID INTEGER,
               FOREIGN KEY(TeacherID) REFERENCES Teachers(TeacherID))''')


cursor.execute("INSERT INTO Teachers (Firstname, Surname, Gender, Email, Role, SubjectID, MasteryID) VALUES ('David', 'Akeredolu', 'M', 'akeredolud@mercia.school', 'A', 1, '')")
cursor.execute("INSERT INTO Teacher_info (TeacherID, phonenumber, personal_email, DOB, qualifications, Emergency_contact, Address, employment_start) VALUES (1, 0123456789, 'davidakeredolu@gmail.com', '1985-06-15', 'MSc  Meachatronics Engineering, PGCE', '07777777777', '123 Meridian Street, London', '2020-09-01')")


cursor.execute("INSERT INTO Subjects (Subjectname) VALUES ('Mathematics')")
cursor.execute("INSERT INTO Subjects (Subjectname) VALUES ('English')")
cursor.execute("INSERT INTO Subjects (Subjectname) VALUES ('Science')")
cursor.execute("INSERT INTO Subjects (Subjectname) VALUES ('Computing')")
cursor.execute("INSERT INTO Subjects (Subjectname) VALUES ('History')")


cursor.execute("INSERT INTO BehaviourTypes (Type) VALUES ('Housepoint')")
cursor.execute("INSERT INTO BehaviourTypes (Type) VALUES ('Demerit')")
cursor.execute("INSERT INTO BehaviourTypes (Type) VALUES ('Detention')")
cursor.execute("INSERT INTO BehaviourTypes (Type) VALUES ('Withdrawal')")

cursor.execute("INSERT INTO Mastery (Masteryname) VALUES ('STEM')")
cursor.execute("INSERT INTO Mastery (Masteryname) VALUES ('FINANCE')")
cursor.execute("INSERT INTO Mastery (Masteryname) VALUES ('ARTS')")
cursor.execute("INSERT INTO Mastery (Masteryname) VALUES ('LAW')")
cursor.execute("INSERT INTO Mastery (Masteryname, Yeargroup) VALUES ('MED1', 12)")
cursor.execute("INSERT INTO Mastery (Masteryname, Yeargroup) VALUES ('MED2', 12)")
cursor.execute("INSERT INTO Mastery (Masteryname, Yeargroup) VALUES ('MED1', 13)")
cursor.execute("INSERT INTO Mastery (Masteryname, Yeargroup) VALUES ('MED2', 13)")


connection.commit()
