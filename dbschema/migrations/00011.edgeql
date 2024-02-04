CREATE MIGRATION m1px6yweovzu6fvwber42m23k7ptxktheh5l2p2ra2ze7vjnv64eva
    ONTO m1chwlfh2ai7sjeuihwvwcn4cy5um7g6vfc3e3ixacirjjswwilgta
{
  ALTER TYPE default::File {
      CREATE REQUIRED PROPERTY modified_at: std::datetime {
          SET REQUIRED USING (std::to_datetime(.mtime));
      };
  };
};
