#!/usr/bin/env python3
import click
from database.db import init_db, get_connection
from backend.auth import create_user, hash_password
import os


@click.group()
def cli():
    """Management commands for the project."""
    pass


@cli.command()
def initdb():
    """Initialize the database schema."""
    report = init_db()
    click.echo("DB initialized")
    click.echo(f"Migrations applied: {len(report['migrations_applied'])}")
    for m in report["migrations_applied"]:
        click.echo(f"  - {m}")
    if report["columns_added"]:
        click.echo("Columns added:")
        for c in report["columns_added"]:
            click.echo(f"  - {c}")
    if report["indexes_added"]:
        click.echo("Indexes added:")
        for i in report["indexes_added"]:
            click.echo(f"  - {i}")


@cli.command()
def seed():
    """Seed students table from data/students folders."""
    data_dir = os.path.join(os.path.dirname(__file__), 'data', 'students')
    conn = get_connection()
    cur = conn.cursor()

    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isdir(path):
            continue
        student_id = name
        exists = cur.execute("SELECT id FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if exists:
            click.echo(f"Skipping existing {student_id}")
            continue

        photo = None
        for fname in os.listdir(path):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                photo = os.path.join('data', 'students', name, fname)
                break

        cur.execute(
            "INSERT INTO students (student_id, name, photo_path) VALUES (?, ?, ?)",
            (student_id, student_id, photo)
        )
        click.echo(f"Inserted {student_id}")

    conn.commit()
    conn.close()


@cli.command()
@click.option("--password", default="pass123", show_default=True, help="Default password for new student logins.")
def init_student_logins(password):
    """Create login accounts for students who don't have users yet."""
    conn = get_connection()
    cur = conn.cursor()

    students = cur.execute("SELECT student_id FROM students").fetchall()
    created = 0
    skipped = 0
    for row in students:
        student_id = row[0]
        exists = cur.execute(
            "SELECT id FROM users WHERE username = ?", (student_id,)
        ).fetchone()
        if exists:
            skipped += 1
            continue

        result = create_user(
            username=student_id,
            password=password,
            role="student",
            student_id=student_id,
        )
        if result.get("success"):
            created += 1
        else:
            click.echo(f"Failed to create login for {student_id}: {result.get('error')}")

    conn.close()
    click.echo(f"Logins created: {created}")
    click.echo(f"Already existed: {skipped}")


@cli.command()
@click.option("--password", default="pass123", show_default=True, help="New password for all student logins.")
def reset_student_passwords(password):
    """Reset ALL student account passwords to the given value."""
    conn = get_connection()
    cur = conn.cursor()

    # Hash once and apply to all student users
    new_hash = hash_password(password)
    cur.execute(
        "UPDATE users SET password_hash = ? WHERE role = 'student'",
        (new_hash,),
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    click.echo(f"Updated passwords for {affected} student users.")


if __name__ == '__main__':
    cli()
