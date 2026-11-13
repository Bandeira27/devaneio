import pytest

from devaneio.rng import Rng


def test_same_seed_same_sequence():
    r1, r2 = Rng(42), Rng(42)
    assert [r1.roll(6) for _ in range(50)] == [r2.roll(6) for _ in range(50)]


def test_different_seeds_differ():
    assert [Rng(1).roll(20) for _ in range(20)] != [Rng(2).roll(20) for _ in range(20)]


def test_replay_from_draw_count_matches_continuation():
    continuous = Rng(7)
    for _ in range(10):
        continuous.roll(6)
    rest = [continuous.roll(6) for _ in range(10)]
    replayed = Rng(7, draws=10)
    assert replayed.draws == 10
    assert [replayed.roll(6) for _ in range(10)] == rest


def test_draws_counts_every_roll():
    r = Rng(3)
    for _ in range(5):
        r.roll(6)
    assert r.draws == 5


def test_roll_is_within_range_and_covers_all_faces():
    r = Rng(2024)
    values = {r.roll(6) for _ in range(500)}
    assert values == {1, 2, 3, 4, 5, 6}


def test_invalid_arguments():
    with pytest.raises(ValueError):
        Rng(1).roll(0)
    with pytest.raises(ValueError):
        Rng(1, draws=-1)


def test_negative_and_huge_seeds_are_accepted():
    assert 1 <= Rng(-1).roll(6) <= 6
    assert 1 <= Rng(2**80).roll(6) <= 6
