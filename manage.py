#!/usr/bin/env python3
import click
from database.db import init_db, get_connection
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


if __name__ == '__main__':
    cli()
