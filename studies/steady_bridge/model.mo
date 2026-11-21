within;
model SteadyBridge
  SimHeat.FixedTemperature hot(T=380);
  SimHeat.FixedTemperature cold(T=280);
  SimHeat.RodArea feed(k=20, L=0.1, A=0.01);
  SimHeat.RodArea drain(k=20, L=0.1, A=0.01);
  SimHeat.RodArea inlet(k=10, L=0.1, A=0.01);
  SimHeat.RodArea outlet(k=10, L=0.1, A=0.01);
  SimHeat.RodArea link(k=10, L=0.1, A=0.01);
equation
  connect(hot.port, feed.port_a);
  connect(hot.port, inlet.port_a);
  connect(feed.port_b, drain.port_a);
  connect(feed.port_b, link.port_a);
  connect(inlet.port_b, outlet.port_a);
  connect(inlet.port_b, link.port_b);
  connect(cold.port, drain.port_b);
  connect(cold.port, outlet.port_b);
end SteadyBridge;
