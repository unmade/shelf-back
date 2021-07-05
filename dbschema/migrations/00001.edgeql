CREATE MIGRATION m1q6xzixv5k67ew46banikezxaoe7qisrr5hecdqdhl2fi2yog6cma
    ONTO initial
{
  CREATE TYPE default::User {
      CREATE REQUIRED PROPERTY password -> std::str;
      CREATE REQUIRED PROPERTY superuser -> std::bool;
      CREATE REQUIRED PROPERTY username -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::Account {
      CREATE REQUIRED SINGLE LINK user -> default::User {
          ON TARGET DELETE  DELETE SOURCE;
      };
      CREATE PROPERTY email -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY first_name -> std::str;
      CREATE REQUIRED PROPERTY last_name -> std::str;
  };
  CREATE TYPE default::MediaType {
      CREATE REQUIRED PROPERTY name -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::Namespace {
      CREATE REQUIRED LINK owner -> default::User {
          ON TARGET DELETE  DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY path -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::File {
      CREATE REQUIRED LINK namespace -> default::Namespace;
      CREATE REQUIRED PROPERTY path -> std::str;
      CREATE CONSTRAINT std::exclusive ON ((.path, .namespace));
      CREATE INDEX ON (std::str_lower(.path));
      CREATE REQUIRED LINK mediatype -> default::MediaType;
      CREATE SINGLE LINK parent -> default::File {
          ON TARGET DELETE  DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY mtime -> std::float64;
      CREATE REQUIRED PROPERTY name -> std::str;
      CREATE REQUIRED PROPERTY size -> std::int64;
  };
};