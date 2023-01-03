CREATE MIGRATION m1epyc5pqoks3kn27jqpgurh5wvyusiqv4lq6jgeafndgc7k65ffia
    ONTO m1y5n46tex3ncob5gzkp732bg4ws66affxip5p4utz7a7i2qgpgqcq
{
  CREATE TYPE default::SharedLink {
      CREATE REQUIRED LINK file -> default::File {
          ON TARGET DELETE DELETE SOURCE;
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY token -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
};
