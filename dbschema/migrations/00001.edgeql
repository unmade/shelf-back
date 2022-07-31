CREATE MIGRATION m1p4m22fjnytfhvnxksltcrdy76g73rhyovlgl6kthrmne3av25hja
    ONTO initial
{
  CREATE TYPE default::MediaType {
      CREATE REQUIRED PROPERTY name -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::Account {
      CREATE PROPERTY email -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY first_name -> std::str;
      CREATE REQUIRED PROPERTY last_name -> std::str;
  };
  CREATE TYPE default::User {
      CREATE REQUIRED PROPERTY password -> std::str;
      CREATE REQUIRED PROPERTY superuser -> std::bool;
      CREATE REQUIRED PROPERTY username -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::Account {
      CREATE REQUIRED SINGLE LINK user -> default::User {
          ON TARGET DELETE DELETE SOURCE;
      };
  };
  CREATE TYPE default::Namespace {
      CREATE REQUIRED LINK owner -> default::User {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY path -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::File {
      CREATE REQUIRED LINK namespace -> default::Namespace;
      CREATE REQUIRED PROPERTY path -> std::str;
      CREATE CONSTRAINT std::exclusive ON ((.path, .namespace));
      CREATE REQUIRED LINK mediatype -> default::MediaType;
      CREATE REQUIRED PROPERTY mtime -> std::float64;
      CREATE REQUIRED PROPERTY name -> std::str;
      CREATE REQUIRED PROPERTY size -> std::int64;
  };
  ALTER TYPE default::User {
      CREATE MULTI LINK bookmarks -> default::File {
          ON TARGET DELETE DELETE SOURCE;
      };
  };
  CREATE TYPE default::FileMetadata {
      CREATE REQUIRED LINK file -> default::File {
          ON TARGET DELETE DELETE SOURCE;
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY data -> std::json;
  };
  CREATE TYPE default::Fingerprint {
      CREATE REQUIRED LINK file -> default::File {
          ON TARGET DELETE DELETE SOURCE;
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY part1 -> std::int32;
      CREATE INDEX ON (.part1);
      CREATE REQUIRED PROPERTY part2 -> std::int32;
      CREATE INDEX ON (.part2);
      CREATE REQUIRED PROPERTY part4 -> std::int32;
      CREATE INDEX ON (.part4);
      CREATE REQUIRED PROPERTY part3 -> std::int32;
      CREATE INDEX ON (.part3);
  };
};
