import sqlite3
from datetime import date, timedelta

LOAN_DAYS = 14      # how long a book can be kept
FINE_PER_DAY = 2    # fine for each late day

# ---------- connect and create tables ----------
connection = sqlite3.connect("library.db")
cursor = connection.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY,
        title TEXT,
        author TEXT,
        category TEXT,
        total_copies INTEGER,
        available INTEGER
    )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY,
        name TEXT,
        phone TEXT
    )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        book_id INTEGER,
        member_id INTEGER,
        issue_date TEXT,
        due_date TEXT,
        return_date TEXT,
        fine INTEGER
    )""")
connection.commit()


# ---------- helper ----------
def get_int(prompt):
    """Keep asking until the user types a whole number."""
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            print("Please enter a number.")


# ---------- books ----------
def add_book():
    title = input("Title: ")
    author = input("Author: ")
    category = input("Category: ")
    copies = get_int("Number of copies: ")

    cursor.execute(
        "INSERT INTO books (title, author, category, total_copies, available) "
        "VALUES (?, ?, ?, ?, ?)",
        (title, author, category, copies, copies),
    )
    connection.commit()
    print("Book added with id", cursor.lastrowid)


def view_books():
    cursor.execute("SELECT id, title, author, category, available, total_copies FROM books")
    rows = cursor.fetchall()
    if not rows:
        print("No books in the library.")
        return
    for r in rows:
        print(f"ID {r[0]} | {r[1]} | {r[2]} | {r[3]} | Available: {r[4]}/{r[5]}")


def search_book():
    keyword = input("Search by title, author or category: ")
    pattern = "%" + keyword + "%"
    cursor.execute(
        "SELECT id, title, author, category, available FROM books "
        "WHERE title LIKE ? OR author LIKE ? OR category LIKE ?",
        (pattern, pattern, pattern),
    )
    rows = cursor.fetchall()
    if not rows:
        print("No matching books.")
        return
    for r in rows:
        print(f"ID {r[0]} | {r[1]} | {r[2]} | {r[3]} | Available: {r[4]}")


# ---------- members ----------
def add_member():
    name = input("Name: ")
    phone = input("Phone: ")
    cursor.execute("INSERT INTO members (name, phone) VALUES (?, ?)", (name, phone))
    connection.commit()
    print("Member added with id", cursor.lastrowid)


def view_members():
    cursor.execute("SELECT id, name, phone FROM members")
    rows = cursor.fetchall()
    if not rows:
        print("No members registered.")
        return
    for r in rows:
        print(f"ID {r[0]} | {r[1]} | {r[2]}")


# ---------- issue and return ----------
def issue_book():
    member_id = get_int("Member id: ")
    book_id = get_int("Book id: ")

    # find the book
    cursor.execute("SELECT id, title, available FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    if book is None:
        print("Book not found.")
        return

    # find the member
    cursor.execute("SELECT id, name FROM members WHERE id = ?", (member_id,))
    member = cursor.fetchone()
    if member is None:
        print("Member not found.")
        return

    # check availability
    if book[2] <= 0:
        print("No copies available right now.")
        return

    # due date
    issue_date = date.today()
    due_date = issue_date + timedelta(days=LOAN_DAYS)

    # save transaction and reduce copies together
    try:
        cursor.execute(
            "INSERT INTO transactions (book_id, member_id, issue_date, due_date) "
            "VALUES (?, ?, ?, ?)",
            (book_id, member_id, issue_date.isoformat(), due_date.isoformat()),
        )
        cursor.execute("UPDATE books SET available = available - 1 WHERE id = ?", (book_id,))
        connection.commit()
    except sqlite3.Error as e:
        connection.rollback()
        print("Something went wrong:", e)
        return

    print(f"'{book[1]}' issued to {member[1]}. Due date: {due_date}")


def return_book():
    member_id = get_int("Member id: ")
    book_id = get_int("Book id: ")

    # find the open (not yet returned) transaction
    cursor.execute(
        "SELECT id, due_date FROM transactions "
        "WHERE book_id = ? AND member_id = ? AND return_date IS NULL",
        (book_id, member_id),
    )
    trans = cursor.fetchone()
    if trans is None:
        print("No active issue found for this member and book.")
        return

    # fine calculation
    due_date = date.fromisoformat(trans[1])
    days_late = (date.today() - due_date).days
    fine = days_late * FINE_PER_DAY if days_late > 0 else 0

    try:
        cursor.execute(
            "UPDATE transactions SET return_date = ?, fine = ? WHERE id = ?",
            (date.today().isoformat(), fine, trans[0]),
        )
        cursor.execute("UPDATE books SET available = available + 1 WHERE id = ?", (book_id,))
        connection.commit()
    except sqlite3.Error as e:
        connection.rollback()
        print("Something went wrong:", e)
        return

    print("Book returned.")
    if fine > 0:
        print(f"Late by {days_late} day(s). Fine: Rs {fine}")
    else:
        print("No fine.")


# ---------- reports ----------
def issued_report():
    cursor.execute(
        "SELECT t.id, b.title, m.name, t.issue_date, t.due_date "
        "FROM transactions t "
        "JOIN books b ON t.book_id = b.id "
        "JOIN members m ON t.member_id = m.id "
        "WHERE t.return_date IS NULL"
    )
    rows = cursor.fetchall()
    if not rows:
        print("No books are currently issued.")
        return
    for r in rows:
        print(f"#{r[0]} | {r[1]} | {r[2]} | Issued: {r[3]} | Due: {r[4]}")


def overdue_report():
    cursor.execute(
        "SELECT t.id, b.title, m.name, t.due_date "
        "FROM transactions t "
        "JOIN books b ON t.book_id = b.id "
        "JOIN members m ON t.member_id = m.id "
        "WHERE t.return_date IS NULL AND t.due_date < ?",
        (date.today().isoformat(),),
    )
    rows = cursor.fetchall()
    if not rows:
        print("No overdue books.")
        return
    for r in rows:
        late = (date.today() - date.fromisoformat(r[3])).days
        print(f"#{r[0]} | {r[1]} | {r[2]} | Due: {r[3]} | {late} day(s) late")


# ---------- menu ----------
def main():
    while True:
        print("\n===== LIBRARY MANAGEMENT =====")
        print("1. Add book")
        print("2. View books")
        print("3. Search book")
        print("4. Add member")
        print("5. View members")
        print("6. Issue book")
        print("7. Return book")
        print("8. Currently issued books")
        print("9. Overdue books")
        print("0. Exit")

        choice = input("Choose: ")

        if choice == "1":
            add_book()
        elif choice == "2":
            view_books()
        elif choice == "3":
            search_book()
        elif choice == "4":
            add_member()
        elif choice == "5":
            view_members()
        elif choice == "6":
            issue_book()
        elif choice == "7":
            return_book()
        elif choice == "8":
            issued_report()
        elif choice == "9":
            overdue_report()
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")

    connection.close()


main()