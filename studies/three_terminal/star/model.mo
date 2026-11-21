within;
model ThreeTerminal
  SimHeat.FixedTemperature warm(T=380);
  SimHeat.FixedTemperature middle(T=330);
  SimHeat.FixedTemperature cool(T=280);
  SimHeat.RodArea first(k=20, L=0.1, A=0.01);
  SimHeat.RodArea second(k=30, L=0.1, A=0.01);
  SimHeat.RodArea third(k=50, L=0.1, A=0.01);
equation
  connect(warm.port, first.port_a);
  connect(middle.port, second.port_a);
  connect(cool.port, third.port_a);
  connect(first.port_b, second.port_b);
  connect(first.port_b, third.port_b);
end ThreeTerminal;
