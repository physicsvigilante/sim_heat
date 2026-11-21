within;
model ThreeTerminal
  SimHeat.FixedTemperature warm(T=380);
  SimHeat.FixedTemperature middle(T=330);
  SimHeat.FixedTemperature cool(T=280);
  SimHeat.RodArea first(k=6, L=0.1, A=0.01);
  SimHeat.RodArea second(k=10, L=0.1, A=0.01);
  SimHeat.RodArea third(k=15, L=0.1, A=0.01);
equation
  connect(warm.port, first.port_a);
  connect(warm.port, second.port_a);
  connect(middle.port, first.port_b);
  connect(middle.port, third.port_a);
  connect(cool.port, second.port_b);
  connect(cool.port, third.port_b);
end ThreeTerminal;
