import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question


MERGES = (
    {
        'parent_uuid': uuid.UUID('53e99f0a-0f0e-56af-9aa1-81e09429c404'),
        'continuation_uuid': uuid.UUID('1d9e96e7-8e9e-5039-ab8f-bd74e6e136ab'),
        'label': '2001 Math III · cofactor quadratic form',
        'prompt': (
            'Let A be an invertible real symmetric n by n matrix, and let A_ij '
            'denote the cofactor of a_ij. Write the quadratic form with '
            'coefficients A_ij/det(A) in matrix form and prove that its matrix '
            'is A^{-1}; then compare its canonical form with that of x^T A x.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('53e99f0a-0f0e-56af-9aa1-81e09429c404'),
        'continuation_uuid': uuid.UUID('d8e5559c-32c4-5811-b8a2-96465b8f3cad'),
        'label': '2001 Math III · cofactor quadratic form',
        'prompt': (
            'Let A be an invertible real symmetric n by n matrix, and let A_ij '
            'denote the cofactor of a_ij. Write the quadratic form with '
            'coefficients A_ij/det(A) in matrix form and prove that its matrix '
            'is A^{-1}; then compare its canonical form with that of x^T A x.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('addc5255-83f7-5ca3-90ce-40dede2b70bd'),
        'continuation_uuid': uuid.UUID('14edfe9f-651a-5293-85c8-d7a3c954f709'),
        'label': '23 Zhang Yu Set 8 · recover a quadratic form',
        'prompt': (
            'A ternary quadratic form x^T A x has orthogonal standard form '
            '2y_1^2-y_2^2-y_3^2 and adj(A) alpha=alpha for '
            'alpha=(1,1,-1)^T. Find the orthogonal matrix Q, recover f, and '
            'find an invertible x=Pz that gives its canonical form.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('addc5255-83f7-5ca3-90ce-40dede2b70bd'),
        'continuation_uuid': uuid.UUID('28c80008-f2f6-5576-b7e1-63af21a4e698'),
        'label': '23 Zhang Yu Set 8 · recover a quadratic form',
        'prompt': (
            'A ternary quadratic form x^T A x has orthogonal standard form '
            '2y_1^2-y_2^2-y_3^2 and adj(A) alpha=alpha for '
            'alpha=(1,1,-1)^T. Find the orthogonal matrix Q, recover f, and '
            'find an invertible x=Pz that gives its canonical form.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('addc5255-83f7-5ca3-90ce-40dede2b70bd'),
        'continuation_uuid': uuid.UUID('d93ad480-d137-57b9-9053-7611173cdecb'),
        'label': '23 Zhang Yu Set 8 · recover a quadratic form',
        'prompt': (
            'A ternary quadratic form x^T A x has orthogonal standard form '
            '2y_1^2-y_2^2-y_3^2 and adj(A) alpha=alpha for '
            'alpha=(1,1,-1)^T. Find the orthogonal matrix Q, recover f, and '
            'find an invertible x=Pz that gives its canonical form.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('f882636d-da3c-589d-b8af-eb3e428b241c'),
        'continuation_uuid': uuid.UUID('a8035411-1ba9-5942-abb7-8f30307aa3ca'),
        'activate_parent': True,
        'label': '24 Zhang Yu Lecture 9 · matrix congruence',
        'prompt': (
            'Let A=[[2,2],[2,a]] and B=[[4,b],[3,1]], where a is a positive '
            'integer. If an invertible C satisfies C^T A C=B, find a and b, '
            'then find one such matrix C.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('f882636d-da3c-589d-b8af-eb3e428b241c'),
        'continuation_uuid': uuid.UUID('a9c30cd9-ea79-5389-b876-aff84398fcf2'),
        'activate_parent': True,
        'label': '24 Zhang Yu Lecture 9 · matrix congruence',
        'prompt': (
            'Let A=[[2,2],[2,a]] and B=[[4,b],[3,1]], where a is a positive '
            'integer. If an invertible C satisfies C^T A C=B, find a and b, '
            'then find one such matrix C.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('ccd18ac8-d8f0-5a45-9be1-9da7c177ae8c'),
        'continuation_uuid': uuid.UUID('9163d89d-ac38-5b7d-af5a-ce7e32aafbfa'),
        'label': '23 Zhang Yu Set 4 · symmetric matrix powers',
        'prompt': (
            'Let A be real symmetric, alpha=(0,-1,1)^T, beta=(1,0,-1)^T, '
            'A alpha=3 beta, and A beta=3 alpha. Suppose rank(AB)<rank(B) for '
            'some B. Orthogonally reduce x^T(A*+A)x, then for gamma=(2,0,-1)^T '
            'find A^n gamma.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('ccd18ac8-d8f0-5a45-9be1-9da7c177ae8c'),
        'continuation_uuid': uuid.UUID('5d066ef5-933d-55b0-9e15-37e5b840fc9b'),
        'label': '23 Zhang Yu Set 4 · symmetric matrix powers',
        'prompt': (
            'Let A be real symmetric, alpha=(0,-1,1)^T, beta=(1,0,-1)^T, '
            'A alpha=3 beta, and A beta=3 alpha. Suppose rank(AB)<rank(B) for '
            'some B. Orthogonally reduce x^T(A*+A)x, then for gamma=(2,0,-1)^T '
            'find A^n gamma.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('a6cc9a65-e063-55b8-8cc3-899ae2ccd213'),
        'continuation_uuid': uuid.UUID('ade8b111-f871-54be-bb43-dd80edde54a5'),
        'label': '23 Zhang Yu Set 1 · simultaneous congruence',
        'prompt': (
            'For f=x_1^2+x_2^2+2x_3^2-2x_1x_3 and '
            'g=x_1^2+2x_3^2-2x_1x_2-2x_1x_3: find C reducing f to standard '
            'form; diagonalize C^TBC orthogonally; then find T that reduces f '
            'and g simultaneously.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('a6cc9a65-e063-55b8-8cc3-899ae2ccd213'),
        'continuation_uuid': uuid.UUID('d24ba6a7-cabc-54d7-994e-a1f7f58e0129'),
        'label': '23 Zhang Yu Set 1 · simultaneous congruence',
        'prompt': (
            'For f=x_1^2+x_2^2+2x_3^2-2x_1x_3 and '
            'g=x_1^2+2x_3^2-2x_1x_2-2x_1x_3: find C reducing f to standard '
            'form; diagonalize C^TBC orthogonally; then find T that reduces f '
            'and g simultaneously.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('a6cc9a65-e063-55b8-8cc3-899ae2ccd213'),
        'continuation_uuid': uuid.UUID('0356eeb2-85a6-5046-8b98-07bcb5373b47'),
        'label': '23 Zhang Yu Set 1 · simultaneous congruence',
        'prompt': (
            'For f=x_1^2+x_2^2+2x_3^2-2x_1x_3 and '
            'g=x_1^2+2x_3^2-2x_1x_2-2x_1x_3: find C reducing f to standard '
            'form; diagonalize C^TBC orthogonally; then find T that reduces f '
            'and g simultaneously.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('df2d23a7-fcb1-5198-840a-cbff5c60ce7b'),
        'continuation_uuid': uuid.UUID('3e95eb8f-c44e-52ef-aee0-706e24946105'),
        'label': '1995 Math III · orthogonal reduction of a quadratic form',
        'prompt': (
            'For f=4x_2^2-3x_3^2+4x_1x_2-4x_1x_3+8x_2x_3, write its '
            'matrix expression, then use an orthogonal transformation to obtain '
            'standard form and give the orthogonal matrix.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('df2d23a7-fcb1-5198-840a-cbff5c60ce7b'),
        'continuation_uuid': uuid.UUID('0fcfcaa0-84e3-5b74-b6d0-d8864b6a7047'),
        'label': '1995 Math III · orthogonal reduction of a quadratic form',
        'prompt': (
            'For f=4x_2^2-3x_3^2+4x_1x_2-4x_1x_3+8x_2x_3, write its '
            'matrix expression, then use an orthogonal transformation to obtain '
            'standard form and give the orthogonal matrix.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('9173cc00-697d-575d-82ad-8334f75a386f'),
        'continuation_uuid': uuid.UUID('ef55f321-975d-549e-b0f9-1cff609bd671'),
        'label': '2003 Math III · quadratic-form invariants',
        'prompt': (
            'Let f=a x_1^2+2x_2^2-2x_3^2+2b x_1x_3 with b>0. The sum of '
            'the eigenvalues of its matrix is 1 and their product is -12. Find '
            'a and b, then orthogonally reduce f to standard form and give Q.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('9173cc00-697d-575d-82ad-8334f75a386f'),
        'continuation_uuid': uuid.UUID('b73ab79b-d643-5ee1-968c-c9ca99e93936'),
        'label': '2003 Math III · quadratic-form invariants',
        'prompt': (
            'Let f=a x_1^2+2x_2^2-2x_3^2+2b x_1x_3 with b>0. The sum of '
            'the eigenvalues of its matrix is 1 and their product is -12. Find '
            'a and b, then orthogonally reduce f to standard form and give Q.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('11d6bd52-6039-5ffd-8a41-f73420f21225'),
        'continuation_uuid': uuid.UUID('428de67b-94da-503e-8db6-d96ec0cc039d'),
        'label': '2001 Math III · singular symmetric system',
        'prompt': (
            'Let A=[[1,1,a],[1,a,1],[a,1,1]] and beta=(1,1,-2)^T. '
            'Given that Ax=beta is consistent but has more than one solution, '
            'find a and an orthogonal Q such that Q^T A Q is diagonal.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('11d6bd52-6039-5ffd-8a41-f73420f21225'),
        'continuation_uuid': uuid.UUID('9e888f44-0e71-56f5-9391-37a52a60deee'),
        'label': '2001 Math III · singular symmetric system',
        'prompt': (
            'Let A=[[1,1,a],[1,a,1],[a,1,1]] and beta=(1,1,-2)^T. '
            'Given that Ax=beta is consistent but has more than one solution, '
            'find a and an orthogonal Q such that Q^T A Q is diagonal.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('0f559514-5189-5d0f-90fa-f537ae502fb2'),
        'continuation_uuid': uuid.UUID('c8b75fbc-a779-5756-a44d-5012d490a7c4'),
        'label': '1996 Math III · four-dimensional orthogonal reduction',
        'prompt': (
            'Let A=diag-block([[0,1],[1,0]],[[y,1],[1,2]]). Given that 3 is '
            'an eigenvalue, find y; then find P such that (AP)^T(AP) is diagonal.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('0f559514-5189-5d0f-90fa-f537ae502fb2'),
        'continuation_uuid': uuid.UUID('83f18f33-f21d-5cca-a90f-654f4c206c9f'),
        'label': '1996 Math III · four-dimensional orthogonal reduction',
        'prompt': (
            'Let A=diag-block([[0,1],[1,0]],[[y,1],[1,2]]). Given that 3 is '
            'an eigenvalue, find y; then find P such that (AP)^T(AP) is diagonal.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('7cc1fa0a-9b29-5e59-ae77-9b1cdfb960af'),
        'continuation_uuid': uuid.UUID('392e166e-d014-5359-83c0-80771777a74d'),
        'label': '1997 Math III · recover a symmetric matrix',
        'prompt': (
            'A real symmetric 3x3 matrix has eigenvalues 1,2,3. Eigenvectors for '
            '1 and 2 are alpha_1=(-1,-1,1)^T and alpha_2=(1,-2,-1)^T. Find an '
            'eigenvector for 3 and determine A.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('7cc1fa0a-9b29-5e59-ae77-9b1cdfb960af'),
        'continuation_uuid': uuid.UUID('d727e2a8-4e0c-5221-baff-afe92ccb7477'),
        'label': '1997 Math III · recover a symmetric matrix',
        'prompt': (
            'A real symmetric 3x3 matrix has eigenvalues 1,2,3. Eigenvectors for '
            '1 and 2 are alpha_1=(-1,-1,1)^T and alpha_2=(1,-2,-1)^T. Find an '
            'eigenvector for 3 and determine A.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('4b81fd06-4f4c-5851-afc2-2581c399f35e'),
        'continuation_uuid': uuid.UUID('2a59308c-9fce-5212-a3aa-5f94d8ae88e0'),
        'label': '25 Zhang Yu Set 5 · quadratic form from an eigenspace',
        'prompt': (
            'The real symmetric matrix of f=x^T A x has eigenvalues 1,1,-1, and '
            'xi=(0,1,1)^T is an eigenvector for -1. Prove that every nonzero vector '
            'orthogonal to xi is an eigenvector for 1, then find the expression for f.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('4b81fd06-4f4c-5851-afc2-2581c399f35e'),
        'continuation_uuid': uuid.UUID('5698c74b-cf6d-57a7-88a1-f43df3923f66'),
        'asset_limit': 1,
        'label': '25 Zhang Yu Set 5 · quadratic form from an eigenspace',
        'prompt': (
            'The real symmetric matrix of f=x^T A x has eigenvalues 1,1,-1, and '
            'xi=(0,1,1)^T is an eigenvector for -1. Prove that every nonzero vector '
            'orthogonal to xi is an eigenvector for 1, then find the expression for f.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('02c7ab24-cd06-5d7d-962a-46a6505fb905'),
        'continuation_uuid': uuid.UUID('0bdfadb7-676a-5751-835a-5b1ddbd2a438'),
        'label': '25 Zhang Yu Set 7 · simultaneous diagonalization',
        'prompt': (
            'Let A and B be 3x3 matrices satisfying AB=2A-B, and suppose A has '
            'three distinct eigenvalues. Prove that AB=BA, and prove that there is '
            'an invertible P such that P^{-1}AP and P^{-1}BP are both diagonal.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('02c7ab24-cd06-5d7d-962a-46a6505fb905'),
        'continuation_uuid': uuid.UUID('99a7dde8-5b36-58a4-856f-189138c04fef'),
        'asset_limit': 1,
        'label': '25 Zhang Yu Set 7 · simultaneous diagonalization',
        'prompt': (
            'Let A and B be 3x3 matrices satisfying AB=2A-B, and suppose A has '
            'three distinct eigenvalues. Prove that AB=BA, and prove that there is '
            'an invertible P such that P^{-1}AP and P^{-1}BP are both diagonal.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('17465e1e-2824-5ec8-9526-22162d12cb52'),
        'continuation_uuid': uuid.UUID('ad2f3103-7fcd-5bb1-a128-a49538db8b11'),
        'label': '2023 Math II/III · diagonalize a linear transformation',
        'prompt': (
            'For every x=(x_1,x_2,x_3)^T, let Ax=(x_1+x_2+x_3, '
            '2x_1-x_2+x_3, x_2-x_3)^T. Find A, then find an invertible matrix P '
            'and diagonal matrix Lambda such that P^{-1}AP=Lambda.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('17465e1e-2824-5ec8-9526-22162d12cb52'),
        'continuation_uuid': uuid.UUID('dc2343fb-4270-5518-a1f4-d9853beaead4'),
        'label': '2023 Math II/III · diagonalize a linear transformation',
        'prompt': (
            'For every x=(x_1,x_2,x_3)^T, let Ax=(x_1+x_2+x_3, '
            '2x_1-x_2+x_3, x_2-x_3)^T. Find A, then find an invertible matrix P '
            'and diagonal matrix Lambda such that P^{-1}AP=Lambda.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('53737c8d-1b0c-5f8f-a7c3-25ef3a536ba9'),
        'continuation_uuid': uuid.UUID('b4ecbe07-28df-57d2-8822-348386fd068f'),
        'label': '25 Zhang Yu Set 6 · diagonalization in a given basis',
        'prompt': (
            'Let alpha_1, alpha_2, alpha_3 be linearly independent and suppose '
            'A alpha_1=-alpha_1-3alpha_2-3alpha_3, '
            'A alpha_2=4alpha_1+4alpha_2+alpha_3, and '
            'A alpha_3=-2alpha_1+3alpha_3. Find an invertible P that diagonalizes A, '
            'then find rank(A-6I).'
        ),
    },
    {
        'parent_uuid': uuid.UUID('53737c8d-1b0c-5f8f-a7c3-25ef3a536ba9'),
        'continuation_uuid': uuid.UUID('b8555818-1197-56ab-99c5-552bb8f34a84'),
        'label': '25 Zhang Yu Set 6 · diagonalization in a given basis',
        'prompt': (
            'Let alpha_1, alpha_2, alpha_3 be linearly independent and suppose '
            'A alpha_1=-alpha_1-3alpha_2-3alpha_3, '
            'A alpha_2=4alpha_1+4alpha_2+alpha_3, and '
            'A alpha_3=-2alpha_1+3alpha_3. Find an invertible P that diagonalizes A, '
            'then find rank(A-6I).'
        ),
    },
    {
        'parent_uuid': uuid.UUID('2cbe828c-cdf3-568e-8bc8-d416436a2d0a'),
        'continuation_uuid': uuid.UUID('c52c13a5-fafb-56b0-9ba8-122ba4aa5443'),
        'label': '1992 Math III · similar matrices with parameters',
        'prompt': (
            'Let A=[[-2,0,0],[2,x,2],[3,1,1]] and B=diag(-1,2,y), and suppose '
            'A and B are similar. Find x and y, then find an invertible matrix P '
            'such that P^{-1} A P=B.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('2cbe828c-cdf3-568e-8bc8-d416436a2d0a'),
        'continuation_uuid': uuid.UUID('b6465fd7-dc24-5874-9434-99756a51b782'),
        'label': '1992 Math III · similar matrices with parameters',
        'prompt': (
            'Let A=[[-2,0,0],[2,x,2],[3,1,1]] and B=diag(-1,2,y), and suppose '
            'A and B are similar. Find x and y, then find an invertible matrix P '
            'such that P^{-1} A P=B.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('3a7f1653-bb98-5536-8154-46c92e7a36bb'),
        'continuation_uuid': uuid.UUID('7ec1d395-1957-5fd4-bee1-addee7a2fcc3'),
        'label': '25 Li Yongle Set 6 · nilpotent chain',
        'prompt': (
            'Let A be a 3x3 matrix and let alpha_1, alpha_2, alpha_3 be three-dimensional '
            'column vectors with alpha_3 nonzero. Suppose A alpha_1=alpha_2, '
            'A alpha_2=alpha_3, and A alpha_3=0. Prove that alpha_1, alpha_2, alpha_3 '
            'are linearly independent; find all eigenvalues and eigenvectors of A; '
            'and compute det(A+2I).'
        ),
    },
    {
        'parent_uuid': uuid.UUID('78b97d07-0e51-5cec-9dbc-444a83355416'),
        'continuation_uuid': uuid.UUID('b3bdf7cf-cd77-5193-bad4-a264ee7501a8'),
        'label': '25 Zhang Yu Set 1 · adjugate matrix relation',
        'prompt': (
            'Let A be an invertible n x n matrix, let A* be its adjugate, and suppose '
            'A B A* = 2 B A^{-1} + I. Prove that AB=BA; prove that A and B have '
            'exactly the same eigenvectors; and determine whether A and B must be similar.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('78b97d07-0e51-5cec-9dbc-444a83355416'),
        'continuation_uuid': uuid.UUID('8e16b3e3-4279-59b1-9e94-f599fc3182a7'),
        'label': '25 Zhang Yu Set 1 · adjugate matrix relation',
        'prompt': (
            'Let A be an invertible n x n matrix, let A* be its adjugate, and suppose '
            'A B A* = 2 B A^{-1} + I. Prove that AB=BA; prove that A and B have '
            'exactly the same eigenvectors; and determine whether A and B must be similar.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('78b97d07-0e51-5cec-9dbc-444a83355416'),
        'continuation_uuid': uuid.UUID('babb72e1-7707-5697-aaa3-133cf05d8147'),
        'label': '25 Zhang Yu Set 1 · adjugate matrix relation',
        'prompt': (
            'Let A be an invertible n x n matrix, let A* be its adjugate, and suppose '
            'A B A* = 2 B A^{-1} + I. Prove that AB=BA; prove that A and B have '
            'exactly the same eigenvectors; and determine whether A and B must be similar.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('3a7f1653-bb98-5536-8154-46c92e7a36bb'),
        'continuation_uuid': uuid.UUID('d68f1957-1bae-558b-8f16-515b380c6b0b'),
        'label': '25 Li Yongle Set 6 · nilpotent chain',
        'prompt': (
            'Let A be a 3x3 matrix and let alpha_1, alpha_2, alpha_3 be three-dimensional '
            'column vectors with alpha_3 nonzero. Suppose A alpha_1=alpha_2, '
            'A alpha_2=alpha_3, and A alpha_3=0. Prove that alpha_1, alpha_2, alpha_3 '
            'are linearly independent; find all eigenvalues and eigenvectors of A; '
            'and compute det(A+2I).'
        ),
    },
    {
        'parent_uuid': uuid.UUID('3a7f1653-bb98-5536-8154-46c92e7a36bb'),
        'continuation_uuid': uuid.UUID('4da15242-0415-5ced-a840-bd9a3501af31'),
        'label': '25 Li Yongle Set 6 · nilpotent chain',
        'prompt': (
            'Let A be a 3x3 matrix and let alpha_1, alpha_2, alpha_3 be three-dimensional '
            'column vectors with alpha_3 nonzero. Suppose A alpha_1=alpha_2, '
            'A alpha_2=alpha_3, and A alpha_3=0. Prove that alpha_1, alpha_2, alpha_3 '
            'are linearly independent; find all eigenvalues and eigenvectors of A; '
            'and compute det(A+2I).'
        ),
    },
    {
        'parent_uuid': uuid.UUID('1a4916e2-32d6-5042-8d9b-7e61311959b7'),
        'continuation_uuid': uuid.UUID('465ec07e-9563-536b-a7cb-5a67c298af84'),
        'label': '1999 Math II · parameterized linear dependence',
        'prompt': (
            'Let alpha_1=(1,1,1,3)^T, alpha_2=(-1,-3,5,1)^T, '
            'alpha_3=(3,2,-1,p+2)^T, and alpha_4=(-2,-6,10,p)^T. '
            'Determine when the vectors are independent and represent (4,1,6,10)^T; '
            'when dependent, find their rank and a maximal independent subset.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('58d909e7-2f21-5aca-8c5e-9d9b6b1b221b'),
        'continuation_uuid': uuid.UUID('76716d65-abc5-58cf-87de-2f0e7e424351'),
        'label': '1990 Math III · five-variable nonhomogeneous system',
        'prompt': (
            'For the displayed four-equation system in five unknowns, determine the '
            'values of a and b for consistency, find a fundamental solution set of '
            'the associated homogeneous system, and give all solutions.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('8a1e0303-5abe-5db0-970d-886ff307f4bb'),
        'continuation_uuid': uuid.UUID('55dfc48f-a805-5ed2-9a82-d12efc7d17d3'),
        'label': '1994 Math III · Vandermonde-type nonhomogeneous system',
        'prompt': (
            'Analyze the displayed Vandermonde-type system. Prove that it is '
            'inconsistent when a_1,a_2,a_3,a_4 are pairwise distinct; then, for '
            'a_1=a_3=k and a_2=a_4=-k, use the two given solutions to write the '
            'general solution.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('c4099e35-66ff-5fbd-b956-94cac5c029df'),
        'continuation_uuid': uuid.UUID('25f29a98-257a-5564-8204-8d97f33e754f'),
        'label': '1994 Math I · common solutions of two homogeneous systems',
        'prompt': (
            'Find whether the displayed four-variable homogeneous systems I and II '
            'have nonzero common solutions, and give all such common solutions.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('5876a6cf-ef78-5a60-b430-0df9bcc88ffc'),
        'continuation_uuid': uuid.UUID('af4e9e05-5d3a-5578-a203-0b62a01999d0'),
        'label': 'Common solutions from a parameterized fundamental solution set',
        'prompt': (
            'The two displayed vectors form a fundamental solution set of system II. '
            'Determine a, then find every nonzero common solution of systems I and II.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('6f6f616a-f921-5707-a63e-79fa0380d898'),
        'continuation_uuid': uuid.UUID('cd699a7d-7de1-5932-84c7-4942c8224f57'),
        'label': '2002 Math II · inverse matrix equation',
        'prompt': 'Prove A-2I is invertible, then solve for A from the displayed B.',
    },
    {
        'parent_uuid': uuid.UUID('6f6f616a-f921-5707-a63e-79fa0380d898'),
        'continuation_uuid': uuid.UUID('d73a7340-785c-5123-94af-fc4d7953d265'),
        'label': '2002 Math II · inverse matrix equation',
        'prompt': 'Prove A-2I is invertible, then solve for A from the displayed B.',
    },
    {
        'parent_uuid': uuid.UUID('c78b98b6-230e-5195-8703-0f3609a2e46d'),
        'continuation_uuid': uuid.UUID('56dc7d7d-1eca-524a-a460-ef0939fcf244'),
        'label': 'Parameterized vector-group representation',
        'prompt': (
            'Determine a and b such that vector group II can be represented by vector '
            'group I, and give the representation coefficients.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('e346967e-521b-59c2-b212-32053353e0b2'),
        'continuation_uuid': uuid.UUID('152403d2-4f4f-532c-bd37-6ed98f501e3a'),
        'label': '1989 Math III · eigenvalues and inverse transform',
        'prompt': 'Find the eigenvalues of A, then find the eigenvalues of I+A^{-1}.',
    },
    {
        'parent_uuid': uuid.UUID('e346967e-521b-59c2-b212-32053353e0b2'),
        'continuation_uuid': uuid.UUID('4f7c9a99-366d-5969-943f-aaf651a65c82'),
        'label': '1989 Math III · eigenvalues and inverse transform',
        'prompt': 'Find the eigenvalues of A, then find the eigenvalues of I+A^{-1}.',
    },
    {
        'parent_uuid': uuid.UUID('f6f73e45-56f5-53e7-a25c-283928c362e5'),
        'continuation_uuid': uuid.UUID('577bc319-8665-5f30-a53c-babaa376e998'),
        'label': '1998 Math III · rank-one nilpotent matrix',
        'prompt': (
            'For nonzero vectors alpha and beta with alpha^T beta=0 and '
            'A=alpha beta^T, find A^2 and all eigenvalues and eigenvectors of A.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('bdb4c67b-c5ad-5386-94b6-b45dacc49252'),
        'continuation_uuid': uuid.UUID('b0df44b5-0d33-525d-aa81-ae5eca8ad333'),
        'label': '2002 Math III · symmetric matrix polynomial',
        'prompt': (
            'A is a real symmetric 3x3 matrix with A^2+2A=0 and rank two. '
            'Find all eigenvalues and determine when A+kI is positive definite.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('bdb4c67b-c5ad-5386-94b6-b45dacc49252'),
        'continuation_uuid': uuid.UUID('99eca915-b0a1-581a-bdf7-0f73758aca35'),
        'label': '2002 Math III · symmetric matrix polynomial',
        'prompt': (
            'A is a real symmetric 3x3 matrix with A^2+2A=0 and rank two. '
            'Find all eigenvalues and determine when A+kI is positive definite.'
        ),
    },
)


class Command(BaseCommand):
    help = 'Merge known page-break continuations in the linear-algebra source.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        changed = 0
        for spec in MERGES:
            try:
                parent = Question.objects.select_for_update().get(uuid=spec['parent_uuid'])
                continuation = Question.objects.select_for_update().get(
                    uuid=spec['continuation_uuid']
                )
            except Question.DoesNotExist as exc:
                raise CommandError(f'Missing continuation pair: {spec}') from exc
            if (
                not continuation.is_practiceable
                and continuation.classification_reason.startswith(
                    'page-break continuation merged into question'
                )
            ):
                continue
            if continuation.attempts.exists():
                raise CommandError(
                    f'Continuation {continuation.uuid} has attempts and cannot be merged safely'
                )
            self.stdout.write(f'Validated continuation {continuation.uuid} -> {parent.uuid}')
            if not options['apply']:
                changed += 1
                continue

            start = parent.assets.count()
            assets = continuation.assets.select_for_update().order_by('position', 'id')
            if spec.get('asset_limit') is not None:
                assets = assets[: spec['asset_limit']]
            for offset, asset in enumerate(assets):
                asset.question = parent
                asset.position = start + offset
                asset.save(update_fields=('question', 'position'))
            parent.display_label = spec['label']
            parent.prompt_text = spec['prompt']
            parent.content_mode = 'image'
            parent.confidence = 0.99
            if spec.get('activate_parent'):
                parent.is_practiceable = True
                parent.record_kind = 'question'
            parent.save(
                update_fields=(
                    'display_label',
                    'prompt_text',
                    'content_mode',
                    'confidence',
                    *(
                        ('is_practiceable', 'record_kind')
                        if spec.get('activate_parent')
                        else ()
                    ),
                )
            )
            continuation.is_practiceable = False
            continuation.record_kind = 'grouped'
            continuation.classification_reason = (
                f'page-break continuation merged into question {parent.uuid}'
            )
            continuation.classification_confidence = 1.0
            continuation.save(
                update_fields=(
                    'is_practiceable',
                    'record_kind',
                    'classification_reason',
                    'classification_confidence',
                )
            )
            changed += 1

        if not options['apply']:
            self.stdout.write(f'Dry run only; {changed} continuation merge(s) are pending.')
            transaction.set_rollback(True)
        else:
            self.stdout.write(self.style.SUCCESS(f'Applied {changed} continuation merge(s).'))
