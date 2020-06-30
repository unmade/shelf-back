import typer

from app import db
from app.auth import crud as auth_crud

cli = typer.Typer()


@cli.command()
def createuser(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True,
    ),
):
    with db.SessionManager() as db_session:
        auth_crud.create(db_session, username, password)
    typer.echo("User created successfully")


if __name__ == "__main__":
    cli()
