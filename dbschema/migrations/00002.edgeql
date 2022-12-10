CREATE MIGRATION m1y5n46tex3ncob5gzkp732bg4ws66affxip5p4utz7a7i2qgpgqcq
    ONTO m1xyxi3so4hlsrouk5vrs75g425ym4ltum2rt7xjfl7w3obbhujwwa
{
  ALTER TYPE default::User {
      ALTER LINK bookmarks {
          ON TARGET DELETE ALLOW;
      };
  };
};
