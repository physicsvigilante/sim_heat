# Twin blocks and a three-rod junction

Post-freeze selection by independent local reviewer Chat B for candidate f05f6a8fbdfd5ac177a5441d22b40dda6bf8e0d4. Original illustrative exercise.

Two isothermal blocks begin at 355 K (amber, mass 0.2 kg, specific heat 300 J/kg/K) and 275 K (blue, 0.15 kg, 400 J/kg/K). Four storage-free rods with constant properties connect them to one another and to a 305 K bath through a massless junction. Each row lists positive orientation and k [W/m/K], length [m], area [m2].

| Rod | Positive direction | k | L | A |
|---|---|---:|---:|---:|
|upper|amber to junction|100|0.1|0.002|
|lower|junction to blue|200|0.12|0.0012|
|feed|bath to junction|80|0.1|0.005|
|link|blue to amber|50|0.1|0.002|

No other heat exchange. At each 0.1 second from 0 to 120 inclusive, determine junction temperature, signed lower flow, blue minus amber temperature, and blue energy gain. Does heat flow in the lower rod reverse while the bath continues absorbing energy?

With p=exp(-t/60) and q=exp(-t/15), the mean block temperature is 305+10p and the amber-minus-blue half difference is 40q. Junction balance gives J=(A+B+2*305)/4=305+5p. The block equations are 60 A'=2(J-A)+(B-A) and 60 B'=2(J-B)+(A-B). Their mean and half-difference decay with the indicated time constants. Hence lower flow is -10p+80q and reverses at 20 ln(8) seconds. Bath supply is -20p W and its signed integral is -1200(1-p) J. Each body integral follows directly from its 60 J/K capacity times its temperature change.

Original per-output budgets use local reference magnitude histories and the policy absolute, relative and ULP rules. Independently check the tighter sufficient absolute bounds 1e-8 K, 1e-8 W, 1e-5 J and 0.64 ULP on static C/G, including at time zero. The Decimal closed form uses 80 digits and a conservative 1e-65 absolute guard for nonconstant expressions. All coefficients are exact small integers and the exponent arguments lie in [-8,0]. Correctly rounded decimal division and exponential each contribute less than 1e-78 absolute here, and subsequent linear combinations and capacity multiplications amplify absolute error by less than 1e5.
