---
name: verifier-avant-push
description: Audit de confidentialité de SkiJo (dépôt public) avant un git push ou pour valider le contenu à publier. Cherche secrets, chemins personnels, e-mails, fichiers lourds ou interdits dans le diff et l'historique. À utiliser avant tout push, après un nouvel import de données, ou quand on demande si le dépôt peut rester public.
---

# Vérifier avant de pousser

Le dépôt est public : tout ce qui est poussé est lisible par tous pour toujours. Cette vérification est en lecture seule ; ne rien réécrire ni pousser sans l'accord de l'utilisateur.

## Étapes

1. **Ce qui part** : `git status -sb`, `git log origin/main..HEAD --format='%h %an <%ae> %s'`, `git diff origin/main..HEAD --stat`.
2. **Identité des commits** : l'adresse d'auteur doit être `38759501+ticoraph@users.noreply.github.com`. Sinon, le signaler (`git config user.email` pour les prochains commits ; la réécriture des commits existants demande l'accord explicite de l'utilisateur).
3. **Hooks** : `uvx pre-commit run --all-files` (gitleaks, clés privées, gros fichiers, chemins personnels, fichiers interdits).
4. **Recherches complémentaires** sur les fichiers versionnés, notebooks et sorties incluses :
   - chemins : `git grep -nIE '(/Users|/home)/[A-Za-z0-9._-]+/'`
   - e-mails : `git grep -nIEio '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}'`. Les adresses de contact d'exploitants de stations déjà présentes dans `extraction_records.jsonl` et `other_information.csv` sont connues ; toute **nouvelle** adresse est à justifier ou à masquer.
   - secrets : `git grep -nIE 'sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|BEGIN [A-Z ]*PRIVATE KEY'`
   - historique : `git log -p origin/main..HEAD | grep -E '^\+' | grep -E '/Users/|api[_-]?key'`
5. **Fichiers** : aucune image ou PDF de plan de piste, aucun `.env` (seul `.env.example` est permis), rien de `data/cache/`, `data/working/` ou `data/maps/` à part les `.gitkeep`. Notebooks : `kernelspec` à `python3`, pas de chemin ni de clé dans les sorties.
6. **Reproductibilité** si des données ou du code ont changé : skill `regenerer-resultats`.
7. **Rapport** : lister ce qui a été vérifié, ce qui a été trouvé (avec fichier et ligne), et ce qui reste à décider. Si un secret est trouvé : dire d'abord de le révoquer chez son fournisseur, avant toute question d'historique.
