---
title: One American put, four solvers
date: 2026-06-10
description: Direct control, penalty methods, and a measured answer to whether Dynamic Chebyshev survives local volatility.
---

Take one unremarkable American put: spot 100, strike 100, one year to expiry, 5% rates, no dividends, 20% volatility. Price it four ways that share no code and barely share vocabulary — a binomial tree, Longstaff–Schwartz Monte Carlo, a Crank–Nicolson finite-difference solver, and the Dynamic Chebyshev method [@glau2019dynamic] that the ChebyshevSharp library ships as a case study. They all print 6.088.

Two questions made me write this post.

First, a puzzle of asymmetry: three of those methods handle early exercise with a trivial pointwise `max`. The fourth needs a nested iterative solver — policy iteration — *inside every time step*, just to apply the same constraint. Why does the same financial feature cost nothing in three methods and an inner loop in the fourth? Working through a Waterloo master's essay on exactly this machinery [@asare2013] finally made the answer click, and it's worth writing down.

Second, a vulnerability I wanted to measure rather than assume: Dynamic Chebyshev leans on knowing the one-step transition density *exactly* (under Black–Scholes, log-returns are Gaussian, so an 8-point Gauss–Hermite rule nails the continuation integral). Local volatility takes that away. Does the method break? I built the experiment, and the answer surprised me twice.

## One equation, four representations

Every method here solves the same backward recursion. At each exercise opportunity,

$$V(S) = \max\big(Q(S,\text{exercise}),\; Q(S,\text{hold})\big),$$

where $Q(S,\text{exercise})$ is the payoff — known, always, for free — and $Q(S,\text{hold})$ is the discounted expectation of the next-step value. The methods differ in exactly one place: **how they represent and compute $Q(\cdot,\text{hold})$.**

The cleanest way I know to see all four at once: the exact one-step operator is $e^{\Delta\tau \mathcal{L}}$, where $\mathcal{L}V = \tfrac{1}{2}\sigma^2 S^2 V_{SS} + rSV_S - rV$ is the Black–Scholes generator. Feynman–Kac says applying the discounted expectation over one step *is* applying this operator. Every method approximates it:

| Method | Approximation of $e^{\Delta\tau \mathcal{L}}$ | Character |
|---|---|---|
| Dynamic Chebyshev | exact — integrate against the transition density (Gauss–Hermite) | explicit, no solve |
| Longstaff–Schwartz | statistical — regress sampled future values | explicit, no solve |
| Explicit FD | $I + \Delta\tau L_h$ — a multiply | explicit, CFL-limited |
| Implicit FD | $(I - \Delta\tau L_h)^{-1}$ — a **divide** | a linear solve per step |

That last row is the entire mystery of "implicit" in one cell. Dividing by a matrix *means* solving a linear system. You can see why anyone would pay for it in the scalar toy problem $dV/dt = -\lambda V$: the explicit step multiplies by $(1-\lambda\Delta t)$, which explodes once $\Delta t > 2/\lambda$; the implicit step divides by $(1+\lambda\Delta t)$, which lies in $(0,1)$ for *any* step size — it inherits the boundedness of the true factor $e^{-\lambda\Delta t}$. On a fine spatial grid, $L_h$ has huge eigenvalues ($\sim \sigma^2 S^2/\Delta S^2$), the explicit ceiling collapses, and implicit stepping is how you stride instead of inch.

## The obstacle, and where policy iteration actually comes from

American exercise adds a floor: $V \ge V^*$ everywhere, where $V^* = \max(K-S, 0)$. In continuous time the value solves a *linear complementarity problem* — equivalently an obstacle problem, equivalently the continuous-time Bellman equation for optimal stopping; three fields, one object:

$$\min\big(V_\tau - \mathcal{L}V,\;\; V - V^*\big) = 0.$$

Read it as a greedy max in residual form: at every point, both "action residuals" are nonnegative and the *smaller* one is zero — either the PDE holds (you're holding) or you're pinned to the payoff (you're exercising).

Now watch what happens when each method enforces the floor.

**If $Q(\cdot,\text{hold})$ is a known function** — Chebyshev's quadrature of the already-computed next step, Longstaff–Schwartz's fitted regression [@longstaff2001], explicit FD's matrix-vector product — then the comparison is between two numbers you already have, at each node independently. The floor costs one pointwise `max`. Done.

**If $Q(\cdot,\text{hold})$ is the output of an implicit solve**, the constraint gets entangled with the unknowns it constrains. Which rows of the linear system should read "PDE holds" and which should read "pinned to payoff" depends on where exercise is optimal — *which is determined by the solution of that very system*. You cannot evaluate the max because one of its inputs depends on the answer. The standard way to break a circularity like this is guess–solve–check:

1. **Guess** the exercise region (a yes/no per node — the *policy*).
2. **Solve** the tridiagonal system with exercise rows pinned and hold rows on the PDE (*policy evaluation*).
3. **Re-ask** at each node whether the other action now wins; flip the violators (*greedy improvement*).
4. Repeat until no node flips. Finite termination: finitely many regions, monotone improvement.

That loop *is* Howard's policy iteration, the same algorithm from every reinforcement-learning textbook, run over a spatial grid inside each time step [@huang2012combined]. The dictionary is exact: grid nodes are states, exercise/hold is the binary action, the exercise region is the policy, the tridiagonal solve is policy evaluation, the flip is greedy improvement.

And here's the control experiment that pins down the cause: the *European* put under implicit FD has the **identical coupled system** — and needs exactly zero iterations, one solve per step. The coupling never forces iteration. The obstacle on top of the coupling does. Three methods avoid the loop not because they're clever about the obstacle, but because their $Q(\text{hold})$ comes pre-computed from the known future, so the obstacle never touches an unknown.

## Direct control vs penalty — and reproducing a 2013 thesis in C#

The Asare essay compares the two principled ways to put the floor *inside* the implicit solve. Both sit on the same finite-difference discretization (positive-coefficient differencing — central where it keeps the off-diagonals nonnegative, upwind otherwise — which guarantees convergence to the viscosity solution; Crank–Nicolson with two fully-implicit startup steps [@rannacher1984] to damp the payoff-kink oscillation):

- **Direct control** writes the LCP as a supremum over an explicit binary control: $\max_{\varphi\in\{0,1\}}\big[\Omega\,\varphi\,(V - V^*) - (1-\varphi)(V_\tau - \mathcal{L}V)\big] = 0$. Exercise rows are pinned exactly; the scheme solves the *exact* discrete LCP. The price of exactness is the scaling factor $\Omega$ (units 1/time): too small and policy iteration stops converging in floating point.
- **Penalty** [@forsyth2002] replaces the hard floor with a stiff spring: $V_\tau - \mathcal{L}V = \tfrac{1}{\varepsilon}\max(V^* - V, 0)$. Solves an *approximation* with $O(\varepsilon)$ penalization error, but starts each step closer to the optimum.

I reimplemented the whole scheme in ~370 lines of dependency-free C# (both handlers behind one enum, Thomas solver, sinh-clustered grid) and validated it on a ladder where each rung isolates one component: European mode first (no obstacle — discretization alone lands $1.2\times10^{-4}$ from the analytic value), then the obstacle (within $1.7\times10^{-3}$ of QLNet's independent FD engine), then the handlers against each other (direct control and penalty agree to $3\times10^{-9}$ — they really do solve the same LCP), then $\Omega$-invariance (changing $\Omega$ by 10× moves the solution by exactly 0.0). Against the essay's own published convergence anchor (a quarter-year put at 2% rates), my solver converges to 3.768257 vs the published 3.76831209 — agreement to $5.5\times10^{-5}$ across thirteen years, two languages, and two grids.

The part that delighted me: the published *iteration mechanics* reproduce exactly. Direct control burns its worst-case iterations in the very first time step — 18 of them, marching the candidate boundary node-by-node out from the strike — while penalty's better starting guess needs at most 6; after that first step the two run neck-and-neck (totals 872 vs 887 over 400 steps, about 2.2 per step). The deeper reason penalty pulls ahead under grid refinement is known [@reisinger2012]: direct control is inherently discrete, while the penalty iteration discretizes a semismooth Newton method on the *continuous* variational inequality, so it has a well-defined limit as the mesh vanishes.

## The experiment: take away the density

Everything so far is the map. Here's the measurement.

Under Black–Scholes, Dynamic Chebyshev's per-step continuation integral is exact because one-step log-returns are Gaussian. Local volatility — $\sigma$ a function of the spot — destroys that: there is no closed-form one-step law to integrate against. This is precisely the regime where the PDE route doesn't even flinch ($\sigma(S_i)$ just lands in the matrix coefficients) and where Longstaff–Schwartz keeps working because it only ever needed simulated paths. The interesting question is what happens to the integral-form method.

**The model.** A CEV-style surface $\sigma(S) = 0.20\,(S/100)^{\beta-1}$, clamped to $[0.05, 0.80]$, with $\beta$ as the knob: $\beta = 1$ *is* geometric Brownian motion (every pricer must reproduce the constant-vol anchors — a built-in wiring check), $\beta = 0.5$ is a moderate smile, $\beta = 0$ a steep one ($\sigma$ doubles to 0.40 by $S=50$).

**The truth bundle.** With no closed form, validation *is* cross-method agreement across independent families. At $\beta = 0.5$, four pricers from three method families agree within about $10^{-3}$:

| Pricer | American put value |
|---|---|
| Hand-rolled FD, direct control | 6.063757 |
| Hand-rolled FD, penalty | 6.063757 (Δ $3\times10^{-9}$) |
| QLNet local-vol FD engine | 6.062995 |
| Longstaff–Schwartz, Euler paths (200k×100, ±0.017) | 6.062937 |

Two validation lessons cost me real debugging time and deserve a public service announcement. One: *the volatility surface grid is part of the model spec* — QLNet consumes σ sampled on a strike grid and interpolates, and densifying that grid from 61 to 121 strikes moved its price by $2.7\times10^{-3}$, which would masquerade as method error if you didn't know to look. Two: *sign heuristics are worthless under local vol* — I confidently predicted "more volatility in the in-the-money region makes the put pricier" and was wrong: the higher ITM vol makes *continuation* more valuable, pushes the exercise boundary down (79.68 vs 80.87 at $\beta=1$, read off the FD solver's policy indicator), and the American came out slightly *cheaper* than flat. Validate by agreement, never by intuition about signs.

**The kernel swap.** To run Dynamic Chebyshev at all under local vol, I gave it the same one-step approximation the Monte Carlo uses: freeze σ at the current state over the step,

$$x' = x + \big(r - q - \tfrac{1}{2}\sigma(x)^2\big)\Delta t + \sqrt{2}\,\sigma(x)\sqrt{\Delta t}\;h_m, \qquad x = \log S,$$

an Euler scheme of weak order one, plugged into the same 8-point Gauss–Hermite rule. The hypothesis writes itself: this injects an $O(\Delta t)$ bias *into the kernel*, where no amount of Chebyshev resolution can reach it. The spectral machinery should converge beautifully — to the wrong answer. The fingerprint to look for: error **plateaus in nodes** at fixed steps, **decays in steps** at fixed nodes.

## What the measurement actually said

**Surprise #1: on the moderate smile, the feared bias is buried under the method's own noise floor.** European leg (no early exercise — the cleanest read), 80 time steps, sweeping Chebyshev nodes, each bias measured against a fine FD reference using the *identical analytic σ*:

| nodes | β=1 bias (kernel exact) | β=0.5 bias (Euler kernel) |
|---|---|---|
| 21 | +0.0849 | +0.0305 |
| 81 | +0.0044 | +0.0045 |
| 161 | −0.00074 | −0.00019 |
| 321 | −0.00086 | **−0.00024** |

Read the bottom row. With the kernel *exact* ($\beta=1$), the method converges to an error of $-8.6\times10^{-4}$ — that's its intrinsic floor: Gauss–Hermite truncation, domain clamping, the terminal payoff kink, and interpolation error compounding across 80 chained steps. With the *frozen* kernel ($\beta=0.5$), the converged error is $-2.4\times10^{-4}$ — **smaller than the floor**. The structural bias is real, but at this smile and step count it's invisible below the noise the method already carries.

The American leg agrees: its error is dominated by the ordinary Bermudan-vs-continuous gap (−0.034 at 20 exercise dates shrinking to −0.0019 at 320, the usual $O(\Delta t)$), exactly like any discrete-exercise method, kernel be damned. And the Greeks — the thing the library exists to compute well — came through the kernel swap essentially untouched: chain-rule Gamma 0.023230 vs the FD grid's 0.023225, agreement at $5\times10^{-6}$, with Delta matching to $2.3\times10^{-4}$.

**Surprise #2: the fingerprint is real — you just need a steep enough smile to see it.** Same measurement on the $\beta=0$ surface, where σ varies fast enough that freezing it over a step actually loses information:

- **Plateau in nodes:** at 80 steps, the bias is +0.00126 at 161 nodes and +0.00130 at 321 nodes. Node-converged, and stuck — the offset that no spectral resolution removes.
- **Decay in steps:** +0.0071 at 20 steps → +0.0013 at 80 → +0.0005 at 320.

That is precisely the predicted signature: the error lives in the kernel, not the interpolant. Both predictions of the structural-bias story are confirmed — and both magnitudes are small enough that the story is "graceful degradation," not failure.

## So what does the PDE route actually buy?

Not headline accuracy on this problem — the four-way table above shows everyone agreeing at the millicent level once each method is given its due. The honest scorecard:

**The FD/LCP route (direct control or penalty) wins on:** models with no tractable transition density *by construction* (zero kernel bias at any steepness — its coefficients just *are* $\sigma(S,t)$); genuinely continuous exercise; provable convergence to the viscosity solution (which starts to matter when the problem becomes a real nonlinear HJB — uncertain volatility, controls richer than stop/go, where the penalty trick doesn't even apply and policy iteration is the only game [@huang2012combined]); and the exercise boundary $B(\tau)$ for free, as the interface of the policy indicator.

**The integral form (Dynamic Chebyshev) wins on:** the offline/online split — you build once and then evaluate price *and analytic Greeks* anywhere, instantly, instead of re-solving per contract; spectral accuracy when the inputs are smooth; and, as measured here, robustness well outside its comfort zone — an off-the-shelf weak-order-one kernel kept prices at the method floor for a moderate smile and preserved Gamma to five decimal places.

**Longstaff–Schwartz wins on:** dimensions, and on never having asked for a density in the first place.

The asymmetry from the opening resolves into one sentence: *the integral form computes $Q(\text{hold})$ first and decides second; the implicit differential form must decide and solve simultaneously — and policy iteration is simply what "deciding while solving" costs.* Once I could see that, the thesis stopped reading as exotic numerics and started reading as the same Bellman backup I'd already implemented twice, wearing PDE clothing.

## Reproducibility

Everything above regenerates from four small console probes (C#/.NET 10), each with PASS/FAIL gates and one command: a QLNet 1.13.1 local-vol smoke test (its `FixedLocalVolSurface` injection path reproduces the constant-vol engine to $9\times10^{-14}$ on a flat surface), the Euler-path Longstaff–Schwartz cross-check, the ~370-line direct-control/penalty solver with its nine-rung validation ladder, and the Dynamic Chebyshev kernel measurement, which links against [ChebyshevSharp](https://github.com/0xC000005/ChebyshevSharp) itself. Total runtime for every number in this post: well under a minute.

## References
