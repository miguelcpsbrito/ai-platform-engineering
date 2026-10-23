# sre/ — operating the platform (Chapter 9)

`runbooks/RB-1` … `RB-5` follow the template of Appendix C.9: every step is an
observation, a decision with criteria, or an action — never "investigate". RB-2
reproduces Table 9.7. The fault-injection layer they are drilled with is
`gateway/platform_gateway/faults.py`; the game day is `labs/ch09`.
