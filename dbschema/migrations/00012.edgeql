CREATE MIGRATION m1pb4ptmqmr3z3djsjjcq5hhip5x3aqebykdbqriscihd5p6ulafsa
    ONTO m1px6yweovzu6fvwber42m23k7ptxktheh5l2p2ra2ze7vjnv64eva
{
  ALTER TYPE default::File {
      DROP PROPERTY mtime;
  };
};
