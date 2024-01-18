CREATE MIGRATION m1qzli3mfxxnswb6uoumt6bhvp6hhdecnpk3jycxe3qr4smkg6yurq
    ONTO m1uql5h7ttpssozd3ta2cq4zaw67usyb7un46sfv6wbst4vcdtkiwa
{
  ALTER TYPE default::File {
      CREATE REQUIRED PROPERTY chash: std::str {
          SET REQUIRED USING (<std::str>'');
      };
      CREATE INDEX ON ((.chash, .namespace));
  };
};
