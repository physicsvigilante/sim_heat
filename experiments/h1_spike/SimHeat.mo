within;
package SimHeat
  "Unqualified H1 spike: thin adapters over MSL thermal components"

  package Units
    function from_degC
      input Real value "Temperature in degree Celsius";
      output Modelica.Units.SI.Temperature result;
    algorithm
      result := value + 273.15;
    end from_degC;

    function from_cm
      input Real value "Length in centimetres";
      output Modelica.Units.SI.Length result;
    algorithm
      result := value / 100.0;
    end from_cm;

    function from_cm2
      input Real value "Area in square centimetres";
      output Modelica.Units.SI.Area result;
    algorithm
      result := value / 10000.0;
    end from_cm2;

    function conductivityFromKcal
      input Real value "Conductivity in kcal/(m.s.K)";
      input Real J_per_kcal "Explicit adopted joules per kilocalorie";
      output Modelica.Units.SI.ThermalConductivity result;
    algorithm
      result := value * J_per_kcal;
    end conductivityFromKcal;
  end Units;

  model Body
    parameter Modelica.Units.SI.Mass m;
    parameter Modelica.Units.SI.SpecificHeatCapacity c;
    parameter Modelica.Units.SI.Temperature T_initial;
    final parameter Modelica.Units.SI.HeatCapacity C = m*c;
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a port;
    Modelica.Units.SI.Temperature T;
    Modelica.Units.SI.HeatFlowRate Q_in;
    Modelica.Units.SI.Energy dU;
  protected
    Modelica.Thermal.HeatTransfer.Components.HeatCapacitor storage(
      C=C, T(start=T_initial, fixed=true));
  equation
    connect(port, storage.port);
    T = storage.T;
    Q_in = storage.port.Q_flow;
    dU = C*(T-T_initial);
  end Body;

  model RodArea
    parameter Modelica.Units.SI.ThermalConductivity k;
    parameter Modelica.Units.SI.Length L;
    parameter Modelica.Units.SI.Area A;
    final parameter Modelica.Units.SI.ThermalConductance G = k*A/L;
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a port_a;
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b port_b;
    Modelica.Units.SI.Temperature T_a;
    Modelica.Units.SI.Temperature T_b;
    Modelica.Units.SI.HeatFlowRate Q_flow "Positive from a to b";
  protected
    Modelica.Thermal.HeatTransfer.Components.ThermalConductor conduction(G=G);
  equation
    connect(port_a, conduction.port_a);
    connect(conduction.port_b, port_b);
    T_a = port_a.T;
    T_b = port_b.T;
    Q_flow = conduction.Q_flow;
  end RodArea;

  model RodCircular
    parameter Modelica.Units.SI.ThermalConductivity k;
    parameter Modelica.Units.SI.Length L;
    parameter Modelica.Units.SI.Diameter d;
    final parameter Modelica.Units.SI.Area A = Modelica.Constants.pi*d*d/4;
    final parameter Modelica.Units.SI.ThermalConductance G = k*A/L;
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_a port_a;
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b port_b;
    Modelica.Units.SI.Temperature T_a;
    Modelica.Units.SI.Temperature T_b;
    Modelica.Units.SI.HeatFlowRate Q_flow "Positive from a to b";
  protected
    RodArea conduction(k=k,L=L,A=A);
  equation
    connect(port_a, conduction.port_a);
    connect(conduction.port_b, port_b);
    T_a = conduction.T_a;
    T_b = conduction.T_b;
    Q_flow = conduction.Q_flow;
  end RodCircular;

  model FixedTemperature
    parameter Modelica.Units.SI.Temperature T;
    Modelica.Thermal.HeatTransfer.Interfaces.HeatPort_b port;
    Modelica.Units.SI.HeatFlowRate Q_to_network
      "Positive for heat supplied by this boundary to its network";
  protected
    Modelica.Thermal.HeatTransfer.Sources.FixedTemperature source(T=T);
  equation
    connect(port, source.port);
    Q_to_network = -source.port.Q_flow;
  end FixedTemperature;
end SimHeat;
