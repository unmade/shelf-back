CREATE MIGRATION m1nzwmkepng3ii74yyhhdrrgihy65ujl7ez7j4jae3eykmxab5sy6q
    ONTO m1epyc5pqoks3kn27jqpgurh5wvyusiqv4lq6jgeafndgc7k65ffia
{
  CREATE TYPE default::AuditTrailAction {
      CREATE REQUIRED PROPERTY name -> std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  CREATE ABSTRACT TYPE default::Auditable;
  CREATE TYPE default::AuditTrail {
      CREATE REQUIRED LINK action -> default::AuditTrailAction {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE MULTI LINK assets -> default::Auditable {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE REQUIRED LINK user -> default::User {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE REQUIRED PROPERTY created_at -> std::datetime;
  };
  ALTER TYPE default::File EXTENDING default::Auditable LAST;
};
