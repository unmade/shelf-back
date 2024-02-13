CREATE MIGRATION m1qvceak5uzotstlfdx7jgimdqzosnprfgxgptcvxjdegrnsdeu5ba
    ONTO m1pb4ptmqmr3z3djsjjcq5hhip5x3aqebykdbqriscihd5p6ulafsa
{
  ALTER TYPE default::Account {
      ALTER LINK user {
          CREATE CONSTRAINT std::exclusive;
          RESET CARDINALITY;
      };
      DROP PROPERTY created_at;
      DROP PROPERTY email;
      DROP PROPERTY first_name;
      DROP PROPERTY last_name;
  };
  ALTER TYPE default::User {
      CREATE REQUIRED PROPERTY active: std::bool {
          SET REQUIRED USING (<std::bool>true);
      };
      CREATE REQUIRED PROPERTY created_at: std::datetime {
          SET REQUIRED USING (<std::datetime>std::datetime_current());
      };
      CREATE REQUIRED PROPERTY display_name: std::str {
          SET REQUIRED USING (<std::str>'');
      };
      CREATE PROPERTY email: std::str {
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY email_verified: std::bool {
          SET REQUIRED USING (<std::bool>false);
      };
      CREATE PROPERTY last_login_at: std::datetime;
  };
};
