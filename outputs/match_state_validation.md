# Match-state validation

- Deliveries: 200,961; innings: 1,712; matches: 867
- Negative balls remaining before a ball: 0; wickets > 10: 0
- Completed chases: 843. Final state agrees with recorded result (chaser won <=> reached target; tie <=> finished one short): **99.6%**
  - Disagreements: 18532 (score 75/4, target 161, outcome tie, dls False); 24822 (score 47/2, target 140, outcome win, dls True); 28334 (score 95/5, target 111, outcome win, dls True)
- Lost chases ending: {'balls used up': 241, 'all out': 164, 'other': 7}
- Won chases finishing with balls to spare: 399 of 422
- First innings (decided matches) ending: {'full quota': 735, 'all out': 98, 'short': 1}
- Outcome types (matches): {'win': 834, 'no_result': 24, 'tie': 9}
- Innings with an inferred (unrecorded) shortened limit: 16; matches flagged state_reliable=False: [18532, 24822, 28334]