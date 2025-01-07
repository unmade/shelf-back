CREATE MIGRATION m1lp5inksydvgqp6mklwlvmh55kiac2cczg6utdsgcvzklusg25z4a
    ONTO m1njadc5meidasveir5mwcx44colyjmkyfctvurkz46lck77q453ca
{
  ALTER TYPE default::Album {
      CREATE REQUIRED PROPERTY slug: std::str {
          SET REQUIRED USING (SELECT
              std::str_lower(.title)
          );
      };
      CREATE CONSTRAINT std::exclusive ON ((.owner, .slug));
      CREATE MULTI LINK items: default::File {
          ON TARGET DELETE ALLOW;
      };
  };
};
