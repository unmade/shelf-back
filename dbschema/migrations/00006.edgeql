CREATE MIGRATION m1uql5h7ttpssozd3ta2cq4zaw67usyb7un46sfv6wbst4vcdtkiwa
    ONTO m1im2dwryygfwlcetbheqkooim3755is6q4wbv25zq2cmg5simvorq
{
  ALTER TYPE default::FileMember {
      CREATE REQUIRED PROPERTY created_at: std::datetime {
          SET REQUIRED USING (<std::datetime>std::datetime_current());
      };
  };
  ALTER TYPE default::SharedLink {
      CREATE REQUIRED PROPERTY created_at: std::datetime {
          SET REQUIRED USING (<std::datetime>std::datetime_current());
      };
  };
};
