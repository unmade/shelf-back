CREATE MIGRATION m1chwlfh2ai7sjeuihwvwcn4cy5um7g6vfc3e3ixacirjjswwilgta
    ONTO m1jmjr7i4m3rxqrjswcbmqnsytx4voqpuwe2khurdfnagyedibtq6a
{
  CREATE TYPE default::FilePendingDeletion {
      CREATE REQUIRED PROPERTY chash: std::str;
      CREATE REQUIRED PROPERTY created_at: std::datetime;
      CREATE REQUIRED PROPERTY mediatype: std::str;
      CREATE REQUIRED PROPERTY ns_path: std::str;
      CREATE REQUIRED PROPERTY path: std::str;
  };
};
