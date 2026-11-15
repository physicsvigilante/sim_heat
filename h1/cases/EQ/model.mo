within;
model H1_EQ
  SimHeat.Body hot(m=1.0,c=500.0,T_initial=308.15);
  SimHeat.Body cold(m=2.0,c=750.0,T_initial=308.15);
  SimHeat.RodArea rod(k=100.0,L=0.5,A=0.001);
equation
  connect(hot.port, rod.port_a);
  connect(rod.port_b, cold.port);
end H1_EQ;
