DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS enrollments;

CREATE TABLE students (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  grade_level INTEGER NOT NULL
);

CREATE TABLE courses (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  teacher TEXT NOT NULL
);

CREATE TABLE enrollments (
  student_id INTEGER NOT NULL,
  course_id INTEGER NOT NULL,
  score INTEGER,
  PRIMARY KEY (student_id, course_id),
  FOREIGN KEY (student_id) REFERENCES students(id),
  FOREIGN KEY (course_id) REFERENCES courses(id)
);

INSERT INTO students (id, name, grade_level) VALUES
  (1, 'Anna Weber', 9),
  (2, 'Luca Stein', 10),
  (3, 'Mia Koch', 9),
  (4, 'Noah Bauer', 11);

INSERT INTO courses (id, title, teacher) VALUES
  (1, 'Mathematik', 'Frau Keller'),
  (2, 'Biologie', 'Herr Wolf'),
  (3, 'Geschichte', 'Frau Reimann');

INSERT INTO enrollments (student_id, course_id, score) VALUES
  (1, 1, 89),
  (1, 2, 95),
  (2, 1, 76),
  (3, 2, 84),
  (4, 3, 91),
  (2, 3, 80);
