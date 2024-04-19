CREATE MIGRATION m1xgo6u6el2sx5ebazgmxk7pzzqym4tf45zf7adxn2ovdmaxvqc6zq
    ONTO m1qvceak5uzotstlfdx7jgimdqzosnprfgxgptcvxjdegrnsdeu5ba
{
  CREATE TYPE default::Album {
      CREATE LINK cover: default::File;
      CREATE REQUIRED LINK owner: default::User {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY created_at: std::datetime;
      CREATE REQUIRED PROPERTY title: std::str;
  };
};
