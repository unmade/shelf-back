CREATE MIGRATION m1njadc5meidasveir5mwcx44colyjmkyfctvurkz46lck77q453ca
    ONTO m1xgo6u6el2sx5ebazgmxk7pzzqym4tf45zf7adxn2ovdmaxvqc6zq
{
  ALTER TYPE default::Album {
      CREATE REQUIRED PROPERTY items_count: std::int32 {
          SET REQUIRED USING (<std::int32>0);
      };
  };
};
