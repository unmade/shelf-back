CREATE MIGRATION m1g2dxh6cjlwcuc26xdfnkatxvi3mfymkpqauc7bxkyqnb77elvfeq
    ONTO m1nzwmkepng3ii74yyhhdrrgihy65ujl7ez7j4jae3eykmxab5sy6q
{
  CREATE TYPE default::Share {
      CREATE REQUIRED LINK file: default::File {
          ON TARGET DELETE DELETE SOURCE;
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE TYPE default::ShareMember {
      CREATE REQUIRED LINK share: default::Share;
      CREATE REQUIRED MULTI LINK user: default::User {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY permissions: std::int16;
  };
  ALTER TYPE default::Share {
      CREATE MULTI LINK members := (.<share[IS default::ShareMember]);
  };
  CREATE TYPE default::ShareMountPoint {
      CREATE REQUIRED LINK member: default::ShareMember {
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED LINK parent: default::File {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY display_name: std::str;
  };
};
