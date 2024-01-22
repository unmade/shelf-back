CREATE MIGRATION m1pr6w4z7nrqbsfkdl5bdqzvpjueerlwtuapswpccq43w6gwnp5w3a
    ONTO m1qzli3mfxxnswb6uoumt6bhvp6hhdecnpk3jycxe3qr4smkg6yurq
{
  CREATE TYPE default::FileCategory {
      CREATE REQUIRED PROPERTY name: std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::File {
      CREATE MULTI LINK categories: default::FileCategory {
          CREATE PROPERTY origin: std::int16;
          CREATE PROPERTY probability: std::int16;
      };
  };
};
