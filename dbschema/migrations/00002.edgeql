CREATE MIGRATION m17lijhawao65manhs3534adaq5ux7dt4rlsmljzpu7ojnhbeahnfq
    ONTO m1w5cg7z7ffj3bmg23ndrnz7o7ccvgo5zhg4zrn64s5f4karnqwqna
{
  CREATE TYPE default::Fingerprint {
      CREATE REQUIRED PROPERTY part1 -> std::int32;
      CREATE INDEX ON (.part1);
      CREATE REQUIRED PROPERTY part2 -> std::int32;
      CREATE INDEX ON (.part2);
      CREATE REQUIRED PROPERTY part4 -> std::int32;
      CREATE INDEX ON (.part4);
      CREATE REQUIRED PROPERTY part3 -> std::int32;
      CREATE INDEX ON (.part3);
      CREATE REQUIRED LINK file -> default::File {
          ON TARGET DELETE  DELETE SOURCE;
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::User {
      ALTER LINK bookmarks {
          ON TARGET DELETE  DELETE SOURCE;
      };
  };
};
