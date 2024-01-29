CREATE MIGRATION m1jmjr7i4m3rxqrjswcbmqnsytx4voqpuwe2khurdfnagyedibtq6a
    ONTO m1pr6w4z7nrqbsfkdl5bdqzvpjueerlwtuapswpccq43w6gwnp5w3a
{
  ALTER TYPE default::File {
      CREATE PROPERTY deleted_at: std::datetime;
  };
};
