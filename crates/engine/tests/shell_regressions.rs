//! Shell regressions found by the robustness fuzzer (tests/robustness/goldens.json).
use serde_json::json;
use solidcraft_engine::Session;

fn run(s: &mut Session, id: &str, p: serde_json::Value) {
    if let Err(e) = s.execute(id, &p) {
        panic!("{id} {p}: {e}");
    }
}

/// Seed 6: a box, a cylinder joined on its side face with the axis on the box's bottom-front
/// edge line (y = 0), then a 1 mm shell open at the bottom. The shell refused a corner where
/// the cylinder meets the box's front and side faces.
///
/// Still open: the corner is a saddle like seed 83's, but one of its faces is the cylinder, and
/// `split_corner` takes planar faces only.
#[test]
#[ignore = "saddle corner with a curved face: split_corner is planar only"]
fn shell_box_with_side_cylinder_on_the_edge_line() {
    let mut s = Session::default();
    run(&mut s, "solid.box", json!({"height": 30.0, "length": 47.5, "width": 45.0}));
    run(&mut s, "solid.cylinder", json!({"axis": [1.0, 0.0, 0.0], "base": [47.5, 0.0, 10.0], "height": 30.0, "operation": "join", "radius": 7.5}));
    run(&mut s, "solid.shell", json!({"faces": [[23.75, 22.5, 0.0]], "thickness": 1.0}));
    let st = s.model.state();
    assert!(s.model.results.iter().all(|r| r.error.is_none()), "{:?}", s.model.results.iter().filter_map(|r| r.error.clone()).collect::<Vec<_>>());
    for b in &st.bodies {
        assert!(b.body.validity().is_empty(), "{:?}", b.body.validity());
    }
}

/// Seed 83: a box on a box, overhanging its back face by 2.5 mm, shelled with the top box's
/// left face open. Where that face meets the lower box's back face, four planar faces meet in a
/// saddle (convex and concave edges in turn). A shell moves the lower box's top and the top
/// box's underside apart (they share a plane, facing opposite ways), so the corner becomes two
/// corners joined by a new edge.
#[test]
fn shell_box_on_box_overhanging_saddle_corner() {
    let mut s = Session::default();
    run(&mut s, "solid.box", json!({"height": 35.0, "length": 25.0, "width": 17.5}));
    run(&mut s, "solid.box", json!({"corner": [7.5, 0.0, 35.0], "height": 7.5, "length": 15.0, "operation": "join", "width": 20.0}));
    let before = volume(&s);
    run(&mut s, "solid.shell", json!({"faces": [[7.5, 17.5, 38.75]], "thickness": 1.5}));
    sound(&s);
    let after = volume(&s);
    // Walls 1.5 mm thick on about 4,500 mm² of faces: roughly 6,700 mm³ of 17,563.
    assert!(after > 0.2 * before && after < 0.6 * before, "shell volume {after} of {before}");
}

fn volume(s: &Session) -> f64 {
    s.model.state().bodies.iter().map(|b| solidcraft_kernel::measure(&b.body).unwrap().volume).sum()
}

fn sound(s: &Session) {
    let errors: Vec<_> = s.model.results.iter().filter_map(|r| r.error.clone()).collect();
    assert!(errors.is_empty(), "{errors:?}");
    let st = s.model.state();
    assert_eq!(st.bodies.len(), 1, "one body");
    for b in &st.bodies {
        assert!(b.body.validity().is_empty(), "{:?}", b.body.validity());
    }
}
