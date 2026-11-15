within;
model H1_D1
  SimHeat.FixedTemperature reservoir(T=353.15);
  SimHeat.RodArea rod(k=100.0,L=0.5,A=0.001);
  SimHeat.Body body(m=1.0,c=500.0,T_initial=293.15);
equation
  connect(reservoir.port, rod.port_a);
  connect(rod.port_b, body.port);
end H1_D1;
