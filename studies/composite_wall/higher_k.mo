within;
model CompositeWall
  SimHeat.FixedTemperature hot(T=380);
  SimHeat.FixedTemperature cold(T=280);
  SimHeat.RodArea facing(k=20, L=0.1, A=0.02);
  SimHeat.RodArea strip(k=10, L=0.1, A=0.01);
  SimHeat.RodArea insert(k=70, L=0.1, A=0.01);
equation
  connect(hot.port, facing.port_a);
  connect(facing.port_b, strip.port_a);
  connect(facing.port_b, insert.port_b);
  connect(strip.port_b, cold.port);
  connect(insert.port_a, cold.port);
end CompositeWall;
