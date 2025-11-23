# Hexagonal Architecture Overview

Hexagonal Architecture (also known as Ports and Adapters) organizes the codebase into layers that separate business logic from technical implementations. The main layers are:

---

## 1. Core (Business Logic / Domain)

- **Description:** The heart of the system. Contains all the business rules and domain logic.
- **Independence:** This layer should not depend on external frameworks or libraries.
- **Example:** Calculating interest on a loan, validating user actions.

---

## 2. Ports (Interfaces)

- **Description:** Abstract definitions (protocols/interfaces) describing how the core communicates with the outside world.
- **Purpose:** Define what should be possible, but not how it's done.
- **Example:**
  
  ```python
  # shared/ports/repository.py
  from abc import ABC, abstractmethod

  class Repository(ABC):
      @abstractmethod
      def get(self, id: str) -> Entity:
          pass

      @abstractmethod
      def insert(self, entity: Entity) -> None:
          pass

      @abstractmethod
      def update(self, entity: Entity) -> None:
          pass
  ```
  *A repository port with basic CRUD contract.*

---

## 3. Adapters (Implementations)

- **Description:** Implement the ports, connecting the app to frameworks, databases, APIs, etc.
- **Example:**
  
  ```python
  # shared/adapters/postgres_repository.py
  from sqlalchemy import create_engine, Column, String
  from sqlalchemy.orm import declarative_base, sessionmaker

  Base = declarative_base()

  class EntityModel(Base):
      __tablename__ = "entities"
      id = Column(String, primary_key=True)
      name = Column(String, nullable=False)
      description = Column(String)

  class PostgresRepository(Repository):
      def __init__(self, db_url: str):
          self.engine = create_engine(db_url)
          Base.metadata.create_all(self.engine)
          self.Session = sessionmaker(bind=self.engine)

      def get(self, id: str) -> Entity:
          session = self.Session()
          try:
              entity = session.query(EntityModel).filter_by(id=id).first()
              if not entity:
                  raise ValueError(f"Entity with id {id} not found")
              return Entity(id=entity.id, name=entity.name, description=entity.description)
          finally:
              session.close()

      def insert(self, entity: Entity) -> None:
          session = self.Session()
          try:
              new_entity = EntityModel(id=entity.id, name=entity.name, description=entity.description)
              session.add(new_entity)
              session.commit()
          finally:
              session.close()

      def update(self, entity: Entity) -> None:
          session = self.Session()
          try:
              model = session.query(EntityModel).filter_by(id=entity.id).first()
              if not model:
                  raise ValueError(f"Entity with id {entity.id} not found")
              model.name = entity.name
              model.description = entity.description
              session.commit()
          finally:
              session.close()
  ```
  *A concrete adapter for PostgreSQL using SQLAlchemy.*

---

## Visualization

- The architecture is often drawn as a hexagon. Each "side" represents a port (interface), and adapters connect to them, decoupling the business logic from technology choices.

---

## Key Concepts

- **Domain:** The specific business area the software addresses.
- **Ubiquitous Language:** Shared vocabulary between developers and domain experts.
- **Entities:** Objects with a distinct identity (e.g., customer, order).
- **Value Objects:** Immutable, identity-less types (e.g., currency, date).
- **Aggregates:** Groups of entities/value objects that change together, with a root entity enforcing invariants.
- **Repositories:** Provide retrieval and persistence for aggregates, via ports.
- **Services:** Standalone operations that don’t fit within a single entity/value object.

---