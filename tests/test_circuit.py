# pylint: disable=invalid-name

import sys
import os
from functools import partial
import numpy as np
import opt_einsum as oem
import pytest
from pytest_lazyfixture import lazy_fixture as lf

# see https://stackoverflow.com/questions/56307329/how-can-i-parametrize-tests-to-run-with-different-fixtures-in-pytest

thisfile = os.path.abspath(__file__)
modulepath = os.path.dirname(os.path.dirname(thisfile))

sys.path.insert(0, modulepath)
import tensorcircuit as tc

# TODO(@refraction-ray):replace all assert np.allclose with np.testing.assert_all_close !


def test_wavefunction():
    qc = tc.Circuit(2)
    qc.apply_double_gate(
        tc.gates.Gate(np.arange(16).reshape(2, 2, 2, 2).astype(np.complex64)), 0, 1
    )
    assert np.real(qc.wavefunction()[2]) == 8
    qc = tc.Circuit(2)
    qc.apply_double_gate(
        tc.gates.Gate(np.arange(16).reshape(2, 2, 2, 2).astype(np.complex64)), 1, 0
    )
    qc.wavefunction()
    assert np.real(qc.wavefunction()[2]) == 4
    qc = tc.Circuit(2)
    qc.apply_single_gate(
        tc.gates.Gate(np.arange(4).reshape(2, 2).astype(np.complex64)), 0
    )
    qc.wavefunction()
    assert np.real(qc.wavefunction()[2]) == 2


def test_basics():
    c = tc.Circuit(2)
    c.x(0)
    assert np.allclose(c.amplitude("10"), np.array(1.0))
    c.CNOT(0, 1)
    assert np.allclose(c.amplitude("11"), np.array(1.0))


def test_measure():
    c = tc.Circuit(3)
    c.H(0)
    c.h(1)
    c.toffoli(0, 1, 2)
    assert c.measure(2)[0] in ["0", "1"]


def test_gates_in_circuit():
    c = tc.Circuit(2, inputs=np.eye(2 ** 2))
    c.iswap(0, 1)
    ans = tc.gates.iswap_gate().tensor.reshape([4, 4])
    np.testing.assert_allclose(c.state().reshape([4, 4]), ans, atol=1e-5)


def test_control_vgate():
    c = tc.Circuit(2)
    c.x(1)
    c.crx(1, 0, theta=0.3)
    np.testing.assert_allclose(
        c.expectation([tc.gates.z(), [0]]), 0.95533645, atol=1e-5
    )


def test_adjoint_gate_circuit():
    c = tc.Circuit(1)
    c.X(0)
    c.SD(0)
    np.testing.assert_allclose(c.state(), np.array([0.0, -1.0j]))


@pytest.mark.parametrize("backend", [lf("tfb"), lf("jaxb")])
def test_jittable_measure(backend):
    @partial(tc.backend.jit, static_argnums=(2, 3))
    def f(param, key, n=6, nlayers=3):
        if key is not None:
            tc.backend.set_random_state(key)
        c = tc.Circuit(n)
        for i in range(n):
            c.H(i)
        for j in range(nlayers):
            for i in range(n - 1):
                c.exp1(i, i + 1, theta=param[2 * j, i], unitary=tc.gates._zz_matrix)
            for i in range(n):
                c.rx(i, theta=param[2 * j + 1, i])
        return c.measure_jit(0, 1, 2, with_prob=True)

    if tc.backend.name == "tensorflow":
        import tensorflow as tf

        print(f(tc.backend.ones([6, 6]), None))
        print(f(tc.backend.ones([6, 6]), None))
        print(f(tc.backend.ones([6, 6]), tf.random.Generator.from_seed(23)))
        print(f(tc.backend.ones([6, 6]), tf.random.Generator.from_seed(24)))
    elif tc.backend.name == "jax":
        import jax

        print(f(tc.backend.ones([6, 6]), jax.random.PRNGKey(23)))
        print(f(tc.backend.ones([6, 6]), jax.random.PRNGKey(24)))

    # As seen here, though I have tried the best, the random API is still not that consistent under jit


@pytest.mark.parametrize("backend", [lf("tfb"), lf("jaxb")])
def test_jittable_depolarizing(backend):
    @tc.backend.jit
    def f1(key):
        n = 5
        if key is not None:
            tc.backend.set_random_state(key)
        c = tc.Circuit(n)
        for i in range(n):
            c.H(i)
        for i in range(n):
            c.cnot(i, (i + 1) % n)
        for i in range(n):
            c.unitary_kraus(
                [
                    tc.gates._x_matrix,
                    tc.gates._y_matrix,
                    tc.gates._z_matrix,
                    tc.gates._i_matrix,
                ],
                i,
                prob=[0.2, 0.2, 0.2, 0.4],
            )
        for i in range(n):
            c.cz(i, (i + 1) % n)
        return c.wavefunction()

    @tc.backend.jit
    def f2(key):
        n = 5
        if key is not None:
            tc.backend.set_random_state(key)
        c = tc.Circuit(n)
        for i in range(n):
            c.H(i)
        for i in range(n):
            c.cnot(i, (i + 1) % n)
        for i in range(n):
            c.unitary_kraus(
                tc.channels.depolarizingchannel(0.2, 0.2, 0.2),
                i,
            )
        for i in range(n):
            c.X(i)
        return c.wavefunction()

    @tc.backend.jit
    def f3(key):
        n = 5
        if key is not None:
            tc.backend.set_random_state(key)
        c = tc.Circuit(n)
        for i in range(n):
            c.H(i)
        for i in range(n):
            c.cnot(i, (i + 1) % n)
        for i in range(n):
            c.depolarizing(i, px=0.2, py=0.2, pz=0.2)
        for i in range(n):
            c.X(i)
        return c.wavefunction()

    @tc.backend.jit
    def f4(key):
        n = 5
        if key is not None:
            tc.backend.set_random_state(key)
        c = tc.Circuit(n)
        for i in range(n):
            c.H(i)
        for i in range(n):
            c.cnot(i, (i + 1) % n)
        for i in range(n):
            c.depolarizing2(i, px=0.2, py=0.2, pz=0.2)
        for i in range(n):
            c.X(i)
        return c.wavefunction()

    @tc.backend.jit
    def f5(key):
        n = 5
        if key is not None:
            tc.backend.set_random_state(key)
        c = tc.Circuit(n)
        for i in range(n):
            c.H(i)
        for i in range(n):
            c.cnot(i, (i + 1) % n)
        for i in range(n):
            c.unitary_kraus2(
                tc.channels.depolarizingchannel(0.2, 0.2, 0.2),
                i,
            )
        for i in range(n):
            c.X(i)
        return c.wavefunction()

    for f in [f1, f2, f3, f4, f5]:
        if tc.backend.name == "tensorflow":
            import tensorflow as tf

            assert np.allclose(tc.backend.norm(f(None)), 1.0, atol=1e-4)
            assert np.allclose(
                tc.backend.norm(f(tf.random.Generator.from_seed(23))), 1.0, atol=1e-4
            )
            assert np.allclose(
                tc.backend.norm(f(tf.random.Generator.from_seed(24))), 1.0, atol=1e-4
            )

        elif tc.backend.name == "jax":
            import jax

            assert np.allclose(
                tc.backend.norm(f(jax.random.PRNGKey(23))), 1.0, atol=1e-4
            )
            assert np.allclose(
                tc.backend.norm(f(jax.random.PRNGKey(24))), 1.0, atol=1e-4
            )


def test_expectation():
    c = tc.Circuit(2)
    c.H(0)
    assert np.allclose(c.expectation((tc.gates.z(), [0])), 0, atol=1e-7)


@pytest.mark.parametrize("backend", [lf("npb"), lf("tfb"), lf("jaxb")])
def test_exp1(backend):
    @partial(tc.backend.jit, jit_compile=True)
    def sf():
        c = tc.Circuit(2)
        xx = np.array(
            [[0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0]], dtype=np.complex64
        )
        c.exp1(0, 1, unitary=xx, theta=tc.num_to_tensor(0.2))
        s = c.state()
        return s

    @tc.backend.jit
    def s1f():
        c = tc.Circuit(2)
        xx = np.array(
            [[0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0]], dtype=np.complex64
        )
        c.exp(0, 1, unitary=xx, theta=tc.num_to_tensor(0.2))
        s1 = c.state()
        return s1

    s = sf()
    s1 = s1f()
    assert np.allclose(s, s1, atol=1e-4)


def test_complex128(highp, tfb):
    c = tc.Circuit(2)
    c.H(1)
    c.rx(0, theta=tc.gates.num_to_tensor(1j))
    c.wavefunction()
    assert np.allclose(c.expectation((tc.gates.z(), [1])), 0)


# def test_qcode():
#     qcode = """
# 4
# x 0
# cnot 0 1
# r 2 theta 1.0 alpha 1.57
# """
#     c = tc.Circuit.from_qcode(qcode)
#     assert c.measure(1)[0] == "1"
#     assert c.to_qcode() == qcode[1:]


def universal_ad():
    @tc.backend.jit
    def forward(theta):
        c = tc.Circuit(2)
        c.R(0, theta=theta, alpha=0.5, phi=0.8)
        return tc.backend.real(c.expectation((tc.gates.z(), [0])))

    gg = tc.backend.grad(forward)
    vg = tc.backend.value_and_grad(forward)
    gg = tc.backend.jit(gg)
    vg = tc.backend.jit(vg)
    theta = tc.gates.num_to_tensor(1.0)
    grad1 = gg(theta)
    v2, grad2 = vg(theta)
    assert grad1 == grad2
    return v2, grad2


@pytest.mark.parametrize("backend", [lf("tfb"), lf("jaxb")])
def test_ad(backend):
    # this amazingly shows how to code once and run in very different AD-ML engines
    print(universal_ad())


def test_single_qubit():
    c = tc.Circuit(1)
    c.H(0)
    w = c.state()[0]
    assert np.allclose(w, np.array([1, 1]) / np.sqrt(2), atol=1e-4)


def test_expectation_between_two_states():
    zp = np.array([1.0, 0.0])
    zd = np.array([0.0, 1.0])
    assert tc.expectation((tc.gates.y(), [0]), ket=zp, bra=zd) == 1j

    c = tc.Circuit(3)
    c.H(0)
    c.ry(1, theta=tc.num_to_tensor(0.8))
    c.cnot(1, 2)

    state = c.wavefunction()
    x1z2 = [(tc.gates.x(), [0]), (tc.gates.z(), [1])]
    e1 = c.expectation(*x1z2)
    e2 = tc.expectation(*x1z2, ket=state, bra=state, normalization=True)
    assert np.allclose(e2, e1)

    c = tc.Circuit(3)
    c.H(0)
    c.ry(1, theta=tc.num_to_tensor(0.8 + 0.7j))
    c.cnot(1, 2)

    state = c.wavefunction()
    x1z2 = [(tc.gates.x(), [0]), (tc.gates.z(), [1])]
    e1 = c.expectation(*x1z2) / tc.backend.norm(state) ** 2
    e2 = tc.expectation(*x1z2, ket=state, normalization=True)
    assert np.allclose(e2, e1)

    c = tc.Circuit(2)
    c.X(1)
    s1 = c.state()
    c2 = tc.Circuit(2)
    c2.X(0)
    s2 = c2.state()
    c3 = tc.Circuit(2)
    c3.H(1)
    s3 = c3.state()
    x1x2 = [(tc.gates.x(), [0]), (tc.gates.x(), [1])]
    e = tc.expectation(*x1x2, ket=s1, bra=s2)
    assert np.allclose(e, 1.0)
    e2 = tc.expectation(*x1x2, ket=s3, bra=s2)
    assert np.allclose(e2, 1.0 / np.sqrt(2))


@pytest.mark.parametrize("backend", [lf("npb"), lf("tfb"), lf("jaxb")])
def test_any_inputs_state(backend):
    c = tc.Circuit(2, inputs=tc.array_to_tensor(np.array([0.0, 0.0, 0.0, 1.0])))
    c.X(0)
    z0 = c.expectation((tc.gates.z(), [0]))
    assert z0 == 1.0
    c = tc.Circuit(2, inputs=tc.array_to_tensor(np.array([0.0, 0.0, 1.0, 0.0])))
    c.X(0)
    z0 = c.expectation((tc.gates.z(), [0]))
    assert z0 == 1.0
    c = tc.Circuit(2, inputs=tc.array_to_tensor(np.array([1.0, 0.0, 0.0, 0.0])))
    c.X(0)
    z0 = c.expectation((tc.gates.z(), [0]))
    assert z0 == -1.0
    c = tc.Circuit(
        2,
        inputs=tc.array_to_tensor(np.array([1 / np.sqrt(2), 0.0, 1 / np.sqrt(2), 0.0])),
    )
    c.X(0)
    z0 = c.expectation((tc.gates.z(), [0]))
    assert np.allclose(z0, 0.0, rtol=1e-4, atol=1e-4)


@pytest.mark.parametrize("backend", [lf("npb"), lf("tfb")])
def test_postselection(backend):
    c = tc.Circuit(3)
    c.H(1)
    c.H(2)
    c.mid_measurement(1, 1)
    c.mid_measurement(2, 1)
    s = c.wavefunction()
    assert np.allclose(tc.backend.real(s[3]), 0.5)


def test_unitary():
    c = tc.Circuit(2, inputs=np.eye(4))
    c.X(0)
    c.Y(1)
    answer = np.kron(tc.gates.x().tensor, tc.gates.y().tensor)
    assert np.allclose(c.wavefunction().reshape([4, 4]), answer, atol=1e-4)


def test_expectation_ps():
    c = tc.Circuit(2)
    c.X(0)
    r = c.expectation_ps(z=[0, 1])
    np.testing.assert_allclose(r, -1, atol=1e-5)

    c = tc.Circuit(2)
    c.H(0)
    r = c.expectation_ps(z=[1], x=[0])
    np.testing.assert_allclose(r, 1, atol=1e-5)


@pytest.mark.parametrize("backend", [lf("tfb"), lf("jaxb")])
def test_dqas_type_circuit(backend):
    eye = tc.gates.i().tensor
    x = tc.gates.x().tensor
    y = tc.gates.y().tensor
    z = tc.gates.z().tensor

    def f(params, structures):
        paramsc = tc.backend.cast(params, dtype="complex64")
        structuresc = tc.backend.softmax(structures, axis=-1)
        structuresc = tc.backend.cast(structuresc, dtype="complex64")
        c = tc.Circuit(5)
        for i in range(5):
            c.H(i)
        for j in range(2):
            for i in range(4):
                c.cz(i, i + 1)
            for i in range(5):
                c.any(
                    i,
                    unitary=structuresc[i, j, 0]
                    * (
                        tc.backend.cos(paramsc[i, j, 0]) * eye
                        + tc.backend.sin(paramsc[i, j, 0]) * x
                    )
                    + structuresc[i, j, 1]
                    * (
                        tc.backend.cos(paramsc[i, j, 1]) * eye
                        + tc.backend.sin(paramsc[i, j, 1]) * y
                    )
                    + structuresc[i, j, 2]
                    * (
                        tc.backend.cos(paramsc[i, j, 2]) * eye
                        + tc.backend.sin(paramsc[i, j, 2]) * z
                    ),
                )
        return tc.backend.real(c.expectation([tc.gates.z(), (2,)]))

    structures = tc.array_to_tensor(
        np.random.normal(size=[16, 5, 2, 3]), dtype="float32"
    )
    params = tc.array_to_tensor(np.random.normal(size=[5, 2, 3]), dtype="float32")

    vf = tc.backend.vmap(f, vectorized_argnums=(1,))

    assert np.allclose(vf(params, structures).shape, [16])

    vvag = tc.backend.vvag(f, argnums=0, vectorized_argnums=1)

    vvag = tc.backend.jit(vvag)

    value, grad = vvag(params, structures)

    assert np.allclose(value.shape, [16])
    assert np.allclose(grad.shape, [5, 2, 3])


@pytest.mark.parametrize("backend", [lf("tfb"), lf("jaxb")])
def test_mixed_measurement_circuit(backend):
    n = 4

    def f(params, structures):
        structuresc = tc.backend.softmax(structures, axis=-1)
        structuresc = tc.backend.cast(structuresc, dtype="complex64")
        c = tc.Circuit(n)
        for i in range(n):
            c.H(i)
        for j in range(2):
            for i in range(n):
                c.cnot(i, (i + 1) % n)
            for i in range(n):
                c.rz(i, theta=params[j, i])
        obs = []
        for i in range(n):
            obs.append(
                [
                    tc.gates.Gate(
                        sum(
                            [
                                structuresc[i, k] * g.tensor
                                for k, g in enumerate(tc.gates.pauli_gates)
                            ]
                        )
                    ),
                    (i,),
                ]
            )
        loss = c.expectation(*obs, reuse=False)
        return tc.backend.real(loss)

    # measure X0 to X3

    structures = tc.backend.cast(tc.backend.eye(n), "int32")
    structures = tc.backend.onehot(structures, num=4)

    f_vvag = tc.backend.jit(tc.backend.vvag(f, vectorized_argnums=1, argnums=0))
    v, g = f_vvag(tc.backend.ones([2, n], dtype="float32"), structures)
    np.testing.assert_allclose(
        v,
        np.array(
            [
                0.015747,
                0.026107,
                0.019598,
                0.025447,
            ]
        ),
        atol=1e-5,
    )
    np.testing.assert_allclose(
        g[0],
        np.array([-0.038279, 0.065810, -0.0018669, 0.035806]),
        atol=1e-5,
    )


def test_circuit_add_demo():
    # to be refactored for better API
    c = tc.Circuit(2)
    c.x(0)
    c2 = tc.Circuit(2, mps_inputs=c.quvector())
    c2.X(0)
    answer = np.array([1.0, 0, 0, 0])
    assert np.allclose(c2.wavefunction(), answer, atol=1e-4)
    c3 = tc.Circuit(2)
    c3.X(0)
    c3.replace_mps_inputs(c.quvector())
    assert np.allclose(c3.wavefunction(), answer, atol=1e-4)


@pytest.mark.parametrize("backend", [lf("npb"), lf("tfb"), lf("jaxb")])
def test_circuit_matrix(backend):
    c = tc.Circuit(2)
    c.x(1)
    c.cnot(0, 1)
    np.testing.assert_allclose(c.matrix()[3], np.array([0.0, 0.0, 0.0, 1.0]), atol=1e-5)
    np.testing.assert_allclose(c.state(), np.array([0, 1.0, 0, 0]), atol=1e-5)


@pytest.mark.parametrize("backend", [lf("tfb"), lf("jaxb")])
def test_circuit_split(backend):
    n = 4

    def f(param, max_singular_values=None, max_truncation_err=None, fixed_choice=None):
        if (max_singular_values is None) and (max_truncation_err is None):
            split = None
        else:
            split = {
                "max_singular_values": max_singular_values,
                "max_truncation_err": max_truncation_err,
                "fixed_choice": fixed_choice,
            }
        c = tc.Circuit(
            n,
            split=split,
        )
        for i in range(n):
            c.H(i)
        for j in range(2):
            for i in range(n - 1):
                c.exp1(i, i + 1, theta=param[2 * j, i], unitary=tc.gates._zz_matrix)
            for i in range(n):
                c.rx(i, theta=param[2 * j + 1, i])
        loss = c.expectation(
            (
                tc.gates.z(),
                [1],
            ),
            (
                tc.gates.z(),
                [2],
            ),
        )
        return tc.backend.real(loss)

    s1 = f(tc.backend.ones([4, n]))
    s2 = f(tc.backend.ones([4, n]), max_truncation_err=1e-5)
    s3 = f(tc.backend.ones([4, n]), max_singular_values=2, fixed_choice=1)

    np.testing.assert_allclose(s1, s2, atol=1e-5)
    np.testing.assert_allclose(s1, s3, atol=1e-5)

    f_jit = tc.backend.jit(f, static_argnums=(1, 2, 3))

    s1 = f_jit(tc.backend.ones([4, n]))
    # s2 = f_jit(tc.backend.ones([4, n]), max_truncation_err=1e-5) # doesn't work now
    # this cannot be done anyway, since variable size tensor network will fail opt einsum
    s3 = f_jit(tc.backend.ones([4, n]), max_singular_values=2, fixed_choice=1)

    # np.testing.assert_allclose(s1, s2, atol=1e-5)
    np.testing.assert_allclose(s1, s3, atol=1e-5)

    f_vg = tc.backend.jit(
        tc.backend.value_and_grad(f, argnums=0), static_argnums=(1, 2, 3)
    )

    s1, g1 = f_vg(tc.backend.ones([4, n]))
    s3, g3 = f_vg(tc.backend.ones([4, n]), max_singular_values=2, fixed_choice=1)

    np.testing.assert_allclose(s1, s3, atol=1e-5)
    # DONE(@refraction-ray): nan on jax backend?
    # i see, complex value SVD is not supported on jax for now :)
    # I shall further customize complex SVD, finally it has applications

    # tf 2.6.2 also doesn't support complex valued SVD AD, weird...
    # if tc.backend.name == "tensorflow":
    np.testing.assert_allclose(g1, g3, atol=1e-5)


@pytest.mark.parametrize("backend", [lf("npb"), lf("tfb"), lf("jaxb")])
def test_gate_split(backend):
    n = 4

    def f(param, max_singular_values=None, max_truncation_err=None, fixed_choice=None):
        if (max_singular_values is None) and (max_truncation_err is None):
            split = None
        else:
            split = {
                "max_singular_values": max_singular_values,
                "max_truncation_err": max_truncation_err,
                "fixed_choice": fixed_choice,
            }
        c = tc.Circuit(
            n,
        )
        for i in range(n):
            c.H(i)
        for j in range(2):
            for i in range(n - 1):
                c.exp1(
                    i,
                    i + 1,
                    theta=param[2 * j, i],
                    unitary=tc.gates._zz_matrix,
                    split=split,
                )
            for i in range(n):
                c.rx(i, theta=param[2 * j + 1, i])
        loss = c.expectation(
            (
                tc.gates.x(),
                [1],
            ),
        )
        return tc.backend.real(loss)

    s1 = f(tc.backend.ones([4, n]))
    s2 = f(tc.backend.ones([4, n]), max_truncation_err=1e-5)
    s3 = f(tc.backend.ones([4, n]), max_singular_values=2, fixed_choice=1)

    np.testing.assert_allclose(s1, s2, atol=1e-5)
    np.testing.assert_allclose(s1, s3, atol=1e-5)


def test_toqir():
    split = {
        "max_singular_values": 2,
        "fixed_choice": 1,
    }
    c = tc.Circuit(3)
    c.H(0)
    c.rx(1, theta=tc.array_to_tensor(0.7))
    c.exp1(
        0, 1, unitary=tc.gates._zz_matrix, theta=tc.array_to_tensor(-0.2), split=split
    )
    z1 = c.expectation((tc.gates.z(), [1]))
    qirs = c.to_qir()
    c = tc.Circuit.from_qir(qirs, circuit_params={"nqubits": 3})
    assert len(c._nodes) == 7
    z2 = c.expectation((tc.gates.z(), [1]))
    np.testing.assert_allclose(z1, z2, atol=1e-5)
    c.append_from_qir(qirs)
    z3 = c.expectation((tc.gates.z(), [1]))
    assert len(c._nodes) == 11
    np.testing.assert_allclose(z3, 0.202728, atol=1e-5)


def test_vis_tex():
    c = tc.Circuit(3)
    for i in range(3):
        c.H(i)
    for i in range(3):
        c.any(i, (i + 1) % 3, unitary=tc.backend.ones([4, 4]), name="hihi")
    c.any(2, unitary=tc.backend.ones([2, 2]), name="invisible")
    c.cz(1, 2)
    c.any(1, 0, 2, unitary=tc.backend.ones([8, 8]), name="ccha")
    c.z(2)
    c.cnot(0, 1)
    c.cz(2, 1)

    print(c.vis_tex(init=["0", "1", ""], measure=["x", "y", "z"]))


def test_debug_contract():
    n = 10
    d = 4
    try:
        import cotengra  # pylint: disable=unused-import

    except ImportError:
        pytest.skip("cotengra is not installed")

    @tc.set_function_contractor(
        "custom_stateful",
        optimizer=oem.RandomGreedy,
        max_time=10,
        max_repeats=64,
        minimize="size",
        debug_level=2,
        contraction_info=True,
    )
    def small_tn():
        param = tc.backend.ones([2 * d, n])
        c = tc.Circuit(n)
        c = tc.templates.blocks.example_block(c, param, nlayers=d)
        return c.state()

    np.testing.assert_allclose(small_tn(), np.zeros([2 ** n]), atol=1e-5)


@pytest.mark.parametrize("backend", [lf("npb"), lf("tfb"), lf("jaxb")])
def test_teleportation(backend):
    key = tc.backend.get_random_state(42)

    @tc.backend.jit
    def f(key):
        tc.backend.set_random_state(key)
        c = tc.Circuit(2)
        c.H(0)
        r = c.cond_measurement(0)
        c.conditional_gate(r, [tc.gates.i(), tc.gates.x()], 1)
        return r, c.expectation([tc.gates.z(), [1]])

    keys = []
    for _ in range(6):
        key, subkey = tc.backend.random_split(key)
        keys.append(subkey)
    rs = [f(k) for k in keys]
    for r, e in rs:
        if tc.backend.numpy(r) > 0.5:
            np.testing.assert_allclose(e, -1, atol=1e-5)
        else:
            np.testing.assert_allclose(e, 1, atol=1e-5)


@pytest.mark.parametrize("backend", [lf("npb"), lf("tfb"), lf("jaxb")])
def test_append_circuit(backend):
    c = tc.Circuit(2)
    c.cnot(0, 1)
    c1 = tc.Circuit(2)
    c1.x(0)
    c.append(c1)
    np.testing.assert_allclose(c.expectation_ps(z=[1]), 1.0)

    c = tc.Circuit(2)
    c.cnot(0, 1)
    c1 = tc.Circuit(2)
    c1.x(0)
    c.prepend(c1)
    np.testing.assert_allclose(c.expectation_ps(z=[1]), -1.0)


@pytest.mark.parametrize("backend", [lf("npb"), lf("tfb"), lf("jaxb")])
def test_apply_mpo_gate(backend):
    gate = tc.gates.multicontrol_gate(tc.gates._x_matrix, ctrl=[1, 0])
    ans = np.array(
        [
            [1.0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1.0, 0, 0, 0, 0, 0, 0],
            [0, 0, 1.0, 0, 0, 0, 0, 0],
            [0, 0, 0, 1.0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 1.0, 0, 0],
            [0, 0, 0, 0, 1.0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 1.0, 0],
            [0, 0, 0, 0, 0, 0, 0, 1.0],
        ]
    )
    c = tc.Circuit(3)
    c.X(0)
    c.mpo(0, 1, 2, mpo=gate.copy())
    np.testing.assert_allclose(c.expectation([tc.gates.z(), [2]]), -1, atol=1e-5)
    c = tc.Circuit(3)
    c.X(1)
    c.mpo(0, 1, 2, mpo=gate.copy())
    np.testing.assert_allclose(c.expectation([tc.gates.z(), [2]]), 1, atol=1e-5)
    np.testing.assert_allclose(gate.eval_matrix(), ans, atol=1e-5)


def test_apply_multicontrol_gate():
    c = tc.Circuit(3)
    c.X(2)
    c.multicontrol(0, 2, 1, ctrl=[0, 1], unitary=tc.gates._x_matrix)
    np.testing.assert_allclose(c.expectation([tc.gates.z(), [1]]), -1, atol=1e-5)
    c = tc.Circuit(3)
    c.X(0)
    c.multicontrol(0, 2, 1, ctrl=[0, 1], unitary=tc.gates._x_matrix)
    np.testing.assert_allclose(c.expectation([tc.gates.z(), [1]]), 1, atol=1e-5)
    c = tc.Circuit(4)
    c.X(0)
    c.X(2)
    c.multicontrol(0, 1, 2, 3, ctrl=[1, 0], unitary=tc.gates.swap())
    np.testing.assert_allclose(c.expectation([tc.gates.z(), [3]]), -1, atol=1e-5)


def test_qir2qiskit():
    try:
        import qiskit.quantum_info as qi
        from tensorcircuit.translation import perm_matrix
    except ImportError:
        pytest.skip("qiskit is not installed")
    # without backend
    n = 6
    c = tc.Circuit(n, inputs=np.eye(2 ** n))
    for i in range(n):
        c.H(i)
    zz = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    for i in range(n):
        c.exp(i, (i + 1) % n, theta=np.random.uniform(), unitary=zz, name="zz")
    c.exp1(1, 3, theta=0.2, unitary=zz, name="zz")
    c.fredkin(1, 2, 3)
    c.swap(0, 1)
    c.iswap(0, 1)
    c.toffoli(0, 1, 2)
    c.s(1)
    c.t(1)
    c.sd(2)
    c.td(2)
    c.x(3)
    c.y(3)
    c.z(3)
    c.wroot(4)
    c.cnot(0, 1)
    c.cy(0, 1)
    c.cz(0, 1)
    c.oy(3, 4)
    c.oz(3, 4)
    c.ox(3, 4)
    c.rx(1, theta=np.random.uniform())
    c.r(5, theta=np.random.uniform())
    c.cr(
        1,
        2,
        theta=np.random.uniform(),
        alpha=np.random.uniform(),
        phi=np.random.uniform(),
    )
    c.ry(1, theta=np.random.uniform())
    c.rz(1, theta=np.random.uniform())
    c.crz(2, 3, theta=np.random.uniform())
    c.crx(5, 3, theta=np.random.uniform())
    c.cry(1, 3, theta=np.random.uniform())
    c.orx(5, 3, theta=np.random.uniform())
    c.ory(5, 3, theta=np.random.uniform())
    c.orz(5, 3, theta=np.random.uniform())
    c.any(1, 3, unitary=np.reshape(zz, [2, 2, 2, 2]))
    gate = tc.gates.multicontrol_gate(tc.gates._x_matrix, ctrl=[1, 0])
    c.mpo(0, 1, 2, mpo=gate.copy())
    c.multicontrol(0, 2, 1, ctrl=[0, 1], unitary=tc.gates._x_matrix, name="x")

    tc_unitary = c.wavefunction()
    tc_unitary = np.reshape(tc_unitary, [2 ** n, 2 ** n])

    qisc = c.to_qiskit()
    qis_unitary = qi.Operator(qisc)
    qis_unitary = np.reshape(qis_unitary, [2 ** n, 2 ** n])

    p_mat = perm_matrix(n)
    np.testing.assert_allclose(p_mat @ tc_unitary @ p_mat, qis_unitary, atol=1e-5)

    # tf backend
    try:
        import tensorflow as tf
    except ImportError:
        pytest.skip("tf is not installed")

    tc.set_backend("tensorflow")
    n = 6
    c = tc.Circuit(n, inputs=tf.eye(2 ** n))

    for i in range(n):
        c.H(i)
    zz = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    for i in range(n):
        c.exp(
            i,
            (i + 1) % n,
            theta=tf.constant(np.random.uniform()),
            unitary=tf.Variable(zz, dtype=tf.complex64),
            name="zz",
        )
    c.exp1(
        1,
        3,
        theta=tf.constant(0.0j),
        unitary=tf.Variable(zz, dtype=tf.complex64),
        name="zz",
    )
    c.fredkin(1, 2, 3)
    c.cswap(1, 2, 3)
    c.ccnot(1, 2, 3)
    c.cx(2, 3)
    c.swap(0, 1)
    c.iswap(0, 1)
    c.toffoli(0, 1, 2)
    c.s(1)
    c.t(1)
    c.sd(1)
    c.td(1)
    c.x(2)
    c.y(2)
    c.z(2)
    c.wroot(3)
    c.cnot(0, 1)
    c.cy(0, 1)
    c.cz(0, 1)
    c.oy(4, 3)
    c.oz(4, 3)
    c.ox(4, 3)
    c.oy(4, 3)
    c.oz(4, 3)
    c.ox(3, 4)
    c.rx(1, theta=tf.constant(np.random.uniform()))
    c.r(5, theta=tf.constant(np.random.uniform()))
    c.cr(
        1,
        2,
        theta=tf.constant(np.random.uniform()),
        alpha=tf.constant(np.random.uniform()),
        phi=tf.constant(np.random.uniform()),
    )
    c.ry(1, theta=tf.constant(np.random.uniform()))
    c.rz(1, theta=tf.constant(np.random.uniform()))
    c.crz(2, 3, theta=tf.constant(np.random.uniform()))
    c.crx(5, 3, theta=tf.constant(np.random.uniform()))
    c.cry(1, 3, theta=tf.constant(np.random.uniform()))
    c.orx(5, 3, theta=tf.constant(np.random.uniform()))
    c.ory(5, 3, theta=tf.constant(np.random.uniform()))
    c.orz(5, 3, theta=tf.constant(np.random.uniform()))
    c.any(1, 3, unitary=tf.constant(np.reshape(zz, [2, 2, 2, 2]), tf.complex64))
    gate = tc.gates.multicontrol_gate(
        tf.constant(tc.gates._x_matrix, tf.complex64), ctrl=[1, 0]
    )
    c.mpo(0, 1, 2, mpo=gate.copy())
    c.multicontrol(
        0,
        2,
        4,
        1,
        5,
        ctrl=[0, 1, 0],
        unitary=tf.constant(tc.gates._zz_matrix, tf.complex64),
        name="zz",
    )

    tc_unitary = c.wavefunction()
    tc_unitary = np.reshape(tc_unitary, [2 ** n, 2 ** n])

    qisc = c.to_qiskit()
    qis_unitary = qi.Operator(qisc)
    qis_unitary = np.reshape(qis_unitary, [2 ** n, 2 ** n])

    p_mat = perm_matrix(n)
    np.testing.assert_allclose(p_mat @ tc_unitary @ p_mat, qis_unitary, atol=1e-5)

    # jax backend
    try:
        import jax.numpy as jnp
    except ImportError:
        pytest.skip("jax is not installed")

    tc.set_backend("jax")

    n = 6
    c = tc.Circuit(n, inputs=jnp.eye(2 ** n))

    # for i in range(n):
    #     c.H(i)
    zz = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    for i in range(n):
        c.exp(
            i,
            (i + 1) % n,
            theta=jnp.array(np.random.uniform()),
            unitary=jnp.array(zz, dtype=jnp.complex64),
            name="zz",
        )
    c.exp1(
        1,
        3,
        theta=jnp.array(np.random.uniform()),
        unitary=jnp.array(zz, dtype=jnp.complex64),
        name="zz",
    )
    c.fredkin(1, 2, 3)
    c.cswap(1, 2, 3)
    c.ccnot(1, 2, 3)
    c.cx(2, 3)
    c.swap(0, 1)
    c.iswap(0, 1)
    c.toffoli(0, 1, 2)
    c.s(1)
    c.t(1)
    c.sd(1)
    c.td(1)
    c.x(2)
    c.y(2)
    c.z(2)
    c.wroot(3)
    c.cnot(0, 1)
    c.cy(0, 1)
    c.cz(0, 1)
    c.oy(4, 3)
    c.oz(4, 3)
    c.ox(4, 3)
    c.oy(4, 3)
    c.oz(4, 3)
    c.ox(3, 4)
    c.rx(1, theta=jnp.array(np.random.uniform()))
    c.r(5, theta=jnp.array(np.random.uniform()))
    c.cr(
        1,
        2,
        theta=jnp.array(np.random.uniform()),
        alpha=tf.constant(np.random.uniform()),
        phi=tf.constant(np.random.uniform()),
    )
    c.ry(1, theta=jnp.array(np.random.uniform(), dtype=jnp.complex64))
    c.rz(1, theta=jnp.array(np.random.uniform()))
    c.crz(2, 3, theta=jnp.array(np.random.uniform()))
    c.crx(5, 3, theta=jnp.array(np.random.uniform()))
    c.cry(1, 3, theta=jnp.array(np.random.uniform()))
    c.orx(5, 3, theta=jnp.array(np.random.uniform()))
    c.ory(5, 3, theta=jnp.array(np.random.uniform()))
    c.orz(5, 3, theta=jnp.array(np.random.uniform()))
    c.any(1, 3, unitary=jnp.array(np.reshape(zz, [2, 2, 2, 2]), jnp.complex64))
    gate = tc.gates.multicontrol_gate(
        jnp.array(tc.gates._x_matrix, jnp.complex64), ctrl=[1, 0]
    )
    c.mpo(0, 1, 2, mpo=gate.copy())
    c.multicontrol(
        0,
        2,
        4,
        1,
        5,
        ctrl=[0, 1, 0],
        unitary=jnp.array(tc.gates._zz_matrix, jnp.complex64),
        name="zz",
    )

    tc_unitary = c.wavefunction()
    tc_unitary = np.reshape(tc_unitary, [2 ** n, 2 ** n])

    qisc = c.to_qiskit()
    qis_unitary = qi.Operator(qisc)
    qis_unitary = np.reshape(qis_unitary, [2 ** n, 2 ** n])

    p_mat = perm_matrix(n)
    np.testing.assert_allclose(p_mat @ tc_unitary @ p_mat, qis_unitary, atol=1e-5)


def test_qiskit2tc():
    try:
        from qiskit import QuantumCircuit
        import qiskit.quantum_info as qi
        from qiskit.circuit.library.standard_gates import MCXGate, SwapGate
        from tensorcircuit.translation import perm_matrix
    except ImportError:
        pytest.skip("qiskit is not installed")
    n = 6
    qisc = QuantumCircuit(n)
    for i in range(n):
        qisc.h(i)
    zz = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    exp_op = qi.Operator(zz)
    for i in range(n):
        qisc.hamiltonian(exp_op, time=np.random.uniform(), qubits=[i, (i + 1) % n])
    qisc.fredkin(1, 2, 3)
    qisc.cswap(1, 2, 3)
    qisc.swap(0, 1)
    qisc.iswap(0, 1)
    qisc.toffoli(0, 1, 2)
    qisc.s(1)
    qisc.t(1)
    qisc.sdg(2)
    qisc.tdg(2)
    qisc.x(3)
    qisc.y(3)
    qisc.z(3)
    qisc.cnot(0, 1)
    qisc.cy(0, 1)
    qisc.cz(0, 1, ctrl_state=0)
    qisc.cy(0, 1, ctrl_state=0)
    qisc.cx(0, 1, ctrl_state=0)
    qisc.rx(np.random.uniform(), 1)
    qisc.ry(np.random.uniform(), 2)
    qisc.rz(np.random.uniform(), 3)
    qisc.crz(np.random.uniform(), 2, 3)
    qisc.crz(np.random.uniform(), 2, 3)
    qisc.crz(np.random.uniform(), 2, 3)
    qisc.crz(np.random.uniform(), 2, 3, ctrl_state=0)
    qisc.crz(np.random.uniform(), 2, 3, ctrl_state=0)
    qisc.crz(np.random.uniform(), 2, 3, ctrl_state=0)
    qisc.unitary(exp_op, [1, 3])
    mcx_g = MCXGate(3, ctrl_state="010")
    qisc.append(mcx_g, [0, 1, 2, 3])
    qisc.ccx(0, 1, 2, ctrl_state="01")
    CCCRX = SwapGate().control(2, ctrl_state="01")
    qisc.append(CCCRX, [0, 1, 2, 3])

    c = tc.Circuit.from_qiskit(qisc, n, np.eye(2 ** n))
    tc_unitary = c.wavefunction()
    tc_unitary = np.reshape(tc_unitary, [2 ** n, 2 ** n])
    qis_unitary = qi.Operator(qisc)
    qis_unitary = np.reshape(qis_unitary, [2 ** n, 2 ** n])
    p_mat = perm_matrix(n)
    np.testing.assert_allclose(p_mat @ tc_unitary @ p_mat, qis_unitary, atol=1e-5)
