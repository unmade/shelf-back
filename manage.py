from __future__ import annotations

import typer

from app import actions, crud, db

cli = typer.Typer()


@cli.command()
def createuser(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, confirmation_prompt=True, hide_input=True,
    ),
) -> None:
    """Creates a new user, namespace, home and trash directories."""
    with db.SessionManager() as db_session:
        actions.create_account(db_session, username, password)
        db_session.commit()
    typer.echo("User created successfully")


@cli.command()
def reconcile() -> None:
    """Reconciles storage and database for all namespaces."""
    with db.SessionManager() as db_session:
        namespaces = crud.namespace.all(db_session)
        for namespace in namespaces:
            actions.reconcile(db_session, namespace, ".")
        db_session.commit()


if __name__ == "__main__":
    cli()
