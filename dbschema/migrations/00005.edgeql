CREATE MIGRATION m1sp6qvzdw4sbo3w2xuanhj7dh2r6zjy6p4ue7s2kne6vqwagstkda
    ONTO m1nzwmkepng3ii74yyhhdrrgihy65ujl7ez7j4jae3eykmxab5sy6q
{
  CREATE TYPE default::FileMember {
      CREATE REQUIRED LINK file: default::File {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE REQUIRED LINK user: default::User {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE CONSTRAINT std::exclusive ON ((.file, .user));
      CREATE REQUIRED PROPERTY permissions: std::int16;
  };
  CREATE TYPE default::FileMemberMountPoint {
      CREATE REQUIRED LINK member: default::FileMember {
          ON TARGET DELETE DELETE SOURCE;
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED LINK parent: default::File {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY display_name: std::str;
  };
};
