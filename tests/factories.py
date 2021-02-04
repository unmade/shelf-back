import factory

from app import db
from app.models.namespace import Namespace
from app.models.user import User

session = db.SessionLocal()


class NamespaceFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Namespace
        sqlalchemy_session = session
        sqlalchemy_session_persistence = "commit"


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    id = factory.Sequence(lambda n: n + 1)
    username = factory.Sequence(lambda n: f"User {n + 1}")
    password = "123"

    namespace = factory.RelatedFactory(
        NamespaceFactory,
        factory_related_name="owner",
        path=factory.SelfAttribute("..username"),
    )

    class Meta:
        model = User
        sqlalchemy_session = session
        sqlalchemy_session_persistence = "commit"
