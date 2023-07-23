CREATE MIGRATION m1im2dwryygfwlcetbheqkooim3755is6q4wbv25zq2cmg5simvorq
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
      CREATE REQUIRED PROPERTY actions: std::int16;
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
