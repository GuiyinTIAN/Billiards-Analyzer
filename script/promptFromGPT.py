import math
from typing import List, Dict, Tuple
from dataclasses import dataclass
import numpy as np
from yolov5.detectbilliards import main, OPT, format_output
import matplotlib.pyplot as plt
import cv2,os
import json


import math
import numpy as np
from typing import List, Dict, Tuple

class BilliardAngleAnalyzer:
    def __init__(self, pockets_config: List[Dict]):
        self.pockets = self._init_pockets(pockets_config)
        self.balls = {}
        self.cue_ball = None
        self._calculate_cushions()

    def _init_pockets(self, configs: List[Dict]) -> List[Dict]:
        pocket_coords = []
        raw_pockets = []
        
        for cfg in configs:
            x = (cfg["bbox"][0] + cfg["bbox"][2]) / 2
            y = (cfg["bbox"][1] + cfg["bbox"][3]) / 2
            radius = min(cfg["bbox"][2]-cfg["bbox"][0], cfg["bbox"][3]-cfg["bbox"][1])/2
            raw_pockets.append({"x": x, "y": y, "cfg": cfg, "radius": radius})
            pocket_coords.append((x, y))

        min_x = min(p[0] for p in pocket_coords)
        max_x = max(p[0] for p in pocket_coords)
        min_y = min(p[1] for p in pocket_coords)
        max_y = max(p[1] for p in pocket_coords)
        width = max_x - min_x
        height = max_y - min_y
        is_longitudinal = width > height

        processed = []
        for p in raw_pockets:
            x_ratio = (p["x"] - min_x) / width if width > 0 else 0
            y_ratio = (p["y"] - min_y) / height if height > 0 else 0
            position = self._determine_pocket_position(x_ratio, y_ratio, is_longitudinal)
            
            processed.append({
                "id": p["cfg"]["id"],
                "position": position,
                "center": (p["x"], p["y"]),
                "radius": p["radius"]
            })
        return processed

    def _calculate_cushions(self):
        all_x = [p["center"][0] for p in self.pockets]
        all_y = [p["center"][1] for p in self.pockets]
        
        corner_pockets = [p for p in self.pockets if "角" in p["position"]]
        if len(corner_pockets) >= 4:
            left_x = min(p["center"][0] for p in corner_pockets)
            right_x = max(p["center"][0] for p in corner_pockets)
            top_y = min(p["center"][1] for p in corner_pockets)
            bottom_y = max(p["center"][1] for p in corner_pockets)
        else:
            left_x = min(all_x)
            right_x = max(all_x)
            top_y = min(all_y)
            bottom_y = max(all_y)
        
        self.cushions = {
            "left": left_x,
            "right": right_x,
            "top": top_y,
            "bottom": bottom_y
        }

    def _determine_pocket_position(self, x_ratio: float, y_ratio: float, is_longitudinal: bool) -> str:
        threshold = 0.25
        mid_threshold = 0.35
        
        if is_longitudinal:
            if x_ratio < threshold:
                if y_ratio < threshold: return "Top-left pocket"
                elif y_ratio > 1 - threshold: return "Bottom-left pocket"
                else: return "Left-middle pocket"
            elif x_ratio > 1 - threshold:
                if y_ratio < threshold: return "Top-right pocket"
                elif y_ratio > 1 - threshold: return "Bottom-right pocket"
                else: return "Right-middle pocket"
            else:
                if y_ratio < mid_threshold: return "Top-middle pocket"
                elif y_ratio > 1 - mid_threshold: return "Bottom-middle pocket"
        else:
            if y_ratio < threshold:
                if x_ratio < threshold: return "Top-left pocket"
                elif x_ratio > 1 - threshold: return "Top-right pocket"
                else: return "Top-middle Pocket"
            elif y_ratio > 1 - threshold:
                if x_ratio < threshold: return "Bottom-left pocket"
                elif x_ratio > 1 - threshold: return "Bottom-right pocket"
                else: return "Bottom-middle pocket"
            else:
                if x_ratio < mid_threshold: return "Left-middle pocket"
                elif x_ratio > 1 - mid_threshold: return "Right-middle pocket"
        return "Unknown pocket"

    def register_ball(self, ball_data: Dict) -> None:
        bbox = ball_data["bbox"]
        self.balls[ball_data["name"]] = {
            "center": ((bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2),
            "radius": (bbox[2]-bbox[0])/2,
            "type": ball_data.get("type", "regular")
        }
        if ball_data.get("type") == "cue":
            self.cue_ball = ball_data["name"]

    def calculate_angles(self) -> Dict:
        results = {}
        if not self.cue_ball:
            return results

        cue_pos = np.array(self.balls[self.cue_ball]["center"])
        
        for ball_name, ball_info in self.balls.items():
            if ball_info["type"] != "regular":
                continue
            
            ball_pos = np.array(ball_info["center"])
            angle_data = {}
            
            for pocket in self.pockets:
                pocket_pos = np.array(pocket["center"])
                angle = self._calculate_vertex_angle(cue_pos, ball_pos, pocket_pos)
                path_blocked = self._check_blocking(cue_pos, ball_pos, pocket_pos, ball_name)
                
                angle_data[pocket["id"]] = {
                    "angle": round(angle, 1),
                    "is_blocked": path_blocked["total_blocked"],
                    "blockers": {
                        "cue_to_ball": path_blocked["cue_to_ball"]["blockers"],
                        "ball_to_pocket": path_blocked["ball_to_pocket"]["blockers"]
                    }
                }
            results[ball_name] = angle_data
        return results

    def _calculate_vertex_angle(self, A: np.ndarray, B: np.ndarray, C: np.ndarray) -> float:
        BA = A - B
        BC = C - B
        dot_product = np.dot(BA, BC)
        mag_BA = np.linalg.norm(BA)
        mag_BC = np.linalg.norm(BC)
        
        if mag_BA == 0 or mag_BC == 0:
            return 0.0
        
        cos_theta = dot_product / (mag_BA * mag_BC)
        return math.degrees(math.acos(np.clip(cos_theta, -1.0, 1.0)))

    def _check_blocking(self, cue_pos: np.ndarray, ball_pos: np.ndarray, 
                      pocket_pos: np.ndarray, current_ball: str) -> Dict:
        cue_to_ball = self._check_segment_blocking(
            cue_pos, ball_pos, 
            exclude={self.cue_ball, current_ball}
        )
        
        ball_to_pocket = self._check_segment_blocking(
            ball_pos, pocket_pos,
            exclude={current_ball, "pocket"}
        )
        
        return {
            "cue_to_ball": {
                "blocked": len(cue_to_ball) > 0,
                "blockers": cue_to_ball
            },
            "ball_to_pocket": {
                "blocked": len(ball_to_pocket) > 0,
                "blockers": ball_to_pocket
            },
            "total_blocked": len(cue_to_ball + ball_to_pocket) > 0
        }

    def _check_segment_blocking(self, start: np.ndarray, end: np.ndarray, exclude: set) -> List[str]:
        blocking = []
        vec = end - start
        mag = np.linalg.norm(vec)
        
        if mag < 1e-6:
            return blocking
            
        for name, ball in self.balls.items():
            if name in exclude:
                continue
                
            center = np.array(ball["center"])
            radius = ball["radius"]
            t = np.dot(center - start, vec) / (mag**2)
            t_clamped = max(0, min(1, t))
            nearest = start + t_clamped * vec
            
            if np.linalg.norm(nearest - center) <= radius:
                blocking.append(name)
        return blocking

    def _distance_between(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        return math.hypot(pos1[0]-pos2[0], pos1[1]-pos2[1])

    def _check_cushion_contact(self, ball_center: Tuple[float, float], radius: float) -> Dict:
        x, y = ball_center
        c = self.cushions
        return {
            "left": (x - (radius+50)) <= c["left"],
            "right": (x + (radius+50)) >= c["right"],
            "top": (y - (radius+50)) <= c["top"],
            "bottom": (y + (radius+50)) >= c["bottom"],
            "any": any([
                (x - (radius+50)) <= c["left"],
                (x + (radius+50)) >= c["right"],
                (y - (radius+50)) <= c["top"],
                (y + (radius+50)) >= c["bottom"]
            ])
        }

    def generate_report(self) -> str:
        analysis = self.calculate_angles()
        report = [
            "# Billiard Path Analysis Report",
            "## Table Configuration",
            f"- Cushion Boundaries | Left:{self.cushions['left']:.1f} Right:{self.cushions['right']:.1f} "
            f"Top:{self.cushions['top']:.1f} Bottom:{self.cushions['bottom']:.1f}",
            "\n## Pocket Locations:"
        ]
        
        for p in self.pockets:
            report.append(f"- {p['position']} (ID:{p['id']}) @ ({p['center'][0]:.1f}, {p['center'][1]:.1f})")
        
        report.append("\n## Ball Analysis")
        for ball_name in self.balls:
            if ball_name == self.cue_ball:
                continue
                
            ball_data = self.balls[ball_name]
            analysis_data = analysis.get(ball_name, {})
            cue_pos = self.balls[self.cue_ball]["center"]
            ball_pos = ball_data["center"]
            
            report.extend([
                f"\n### Ball {ball_name}",
                f"- Position: ({ball_pos[0]:.1f}, {ball_pos[1]:.1f})",
                f"- Distance from Cue: {self._distance_between(cue_pos, ball_pos):.1f}",
                f"- Cushion Contact: {self._format_cushion_status(self._check_cushion_contact(ball_pos, ball_data['radius']))}"
            ])
            
            for pid, path_info in analysis_data.items():
                pocket = next((p for p in self.pockets if str(p["id"]) == str(pid)), None)
                pos_name = pocket["position"] if pocket else f"Pocket{pid}"
                pocket_distance = self._distance_between(ball_pos, pocket["center"]) if pocket else 0
                
                cue_block = path_info['blockers']['cue_to_ball']
                pocket_block = path_info['blockers']['ball_to_pocket']
                
                report.append(
                    f"  → {pos_name}: Angle {path_info['angle']:.1f}° | "
                    f"Distance {pocket_distance:.1f}\n"
                    f"     Cue Path: [{', '.join(cue_block) if cue_block else 'Clear'}] "
                    f"{'⚠️' if cue_block else '✅'}\n"
                    f"     Pocket Path: [{', '.join(pocket_block) if pocket_block else 'Clear'}] "
                    f"{'⛔' if pocket_block else '🟢'}"
                )
        
        return "\n".join(report)

    def _format_cushion_status(self, status: Dict) -> str:
        if not status["any"]:
            return "Not touching cushion"
        directions = []
        if status["left"]: directions.append("left")
        if status["right"]: directions.append("right")
        if status["top"]: directions.append("top")
        if status["bottom"]: directions.append("bottom")
        return f"Touching {', '.join(directions)} cushion(s)"

    def generate_analysis_json(self) -> dict:
        analysis = self.calculate_angles()
        
        return {
            "table_configuration": {
                "cushion_boundaries": {
                    "left": round(self.cushions["left"], 1),
                    "right": round(self.cushions["right"], 1),
                    "top": round(self.cushions["top"], 1),
                    "bottom": round(self.cushions["bottom"], 1)
                },
                "pockets": [
                    {
                        "id": p["id"],
                        "position_type": p["position"],
                        "coordinates": [
                            round(p["center"][0], 1),
                            round(p["center"][1], 1)
                        ]
                    } for p in self.pockets
                ]
            },
            "ball_analysis": [
                {
                    "ball_id": ball_name,
                    "position": [
                        round(ball_data["center"][0], 1),
                        round(ball_data["center"][1], 1)
                    ],
                    "distance_from_cue": round(
                        self._distance_between(
                            self.balls[self.cue_ball]["center"],
                            ball_data["center"]
                        ), 1
                    ),
                    "cushion_contact": self._format_cushion_status_json(
                        self._check_cushion_contact(
                            ball_data["center"],
                            ball_data["radius"]
                        )
                    ),
                    "target_paths": [
                        {
                            "target_pocket_id": pid,
                            "attack_angle": path_info["angle"],
                            "distance_to_pocket": round(
                                self._distance_between(
                                    ball_data["center"],
                                    next(
                                        p["center"] for p in self.pockets 
                                        if str(p["id"]) == str(pid)
                                    )
                                ), 1
                            ) if any(p["id"] == pid for p in self.pockets) else 0.0,
                            "path_blockers": {
                                "cue_to_ball": path_info["blockers"]["cue_to_ball"],
                                "ball_to_pocket": path_info["blockers"]["ball_to_pocket"]
                            }
                        } for pid, path_info in analysis.get(ball_name, {}).items()
                    ]
                } for ball_name, ball_data in self.balls.items()
                if ball_name != self.cue_ball
            ]
        }

    def _format_cushion_status_json(self, status: dict) -> dict:
        return {
            "is_touching": status["any"],
            "touching_sides": [
                side for side in ["left", "right", "top", "bottom"] 
                if status[side]
            ],
            "description": self._format_cushion_status(status)
        }
    
    def generate_analysis_json(self) -> dict:
        """Generate analysis data containing split-path blocking information"""
        analysis = self.calculate_angles()
        
        return {
            "system_context": {
                "role": "you are an American 9-ball analyst, you need to give advice to player after analysis the ball distribution on the table, basic information of the ball distribution will be given",
                "game_type": "American 9-Ball",
                "rules": {
                    "key rule": "the cue ball cannot touch the ball which is not the lowest number first no matter when you are attcking or defensing!!!",
                    "angle analysis": "attack_angle of 180 degree is a straight line, attack_angle has degree between 0 to 100 degree is impossible, very very difficulty to attack, this kind of attack should not appear in your analysis even as alternative choice, attack_angle degree between 150 and 180 is easy to attack, but the distance between ball to cue ball and distance  between ball to pocket also need to be considered, attack_angle has degree between 100 and 150 is difficulty to attack, when the target ball is close to pocket, it would be easier",
                    "ball_order": "have to start with the ball with the lowest number, the cue ball must touch the ball with lowest number first, cue ball cannot touch ball that is not the lowest number even you want to do the safety shot, if the cue ball touch the ball which is not the lowest number, it is foul and give the ball to opponent",
                    "continuous shotting": "As long as the lowest numbered ball on the table is contacted first by the cueball, and any one or more of the object balls are pocketed in any of the pockets with no foul being committed, a player's inning continues.",
                    "win_condition": "The winner is the player who legally pockets the nine-ball, the game's money ball, regardless of how many balls have been pocketed beforehand. You cannot pockets the nine-ball before all the other balls have been pocketed.",
                    "foul_penalty": "Opponents gain possession of the ball"
                },
                "analysis_priorities": [
                    "route analysis",
                    "possibility to continous attack",
                    "advice for safety shot",
                    "the position of blocking ball will be given, it is impossible for the cue ball to hit the target ball directly when there is a blocking ball between cue bal and target ball"
                ],
                "attack_analysis": [
                    "It is difficulty to attack (better to start defense) for the ball that is close to cushion,"
                    "or the angle is smaller than 140 degree,"
                    "or the distance is long between ball and cue ball or pocket",
                    "It is impossible to attack (must start defense) when the path between the ball and pocket is blocked by other ball,"
                    "or the angle is smaller than 90 degree"
                ],
                "defense_strategy": [
                    "the cue ball cannot touch ball which is not the lowest number one first, if you do so, it is foul",
                    "when you choose defense, it means you cannot make the target ball into pocket, "
                    "the goal of defense is making the opponent does not get a good chance to attack, "
                    "for example, make the cue ball or target ball close to cushion, "
                    "or leave a angle which is impossible to attack, "
                    "the best situation is to control the position of cue ball and target so that there is a blocking ball in between."
                ]
            },
            "table_state": {
                "dimensions": {
                    "left": round(self.cushions["left"], 1),
                    "right": round(self.cushions["right"], 1),
                    "top": round(self.cushions["top"], 1),
                    "bottom": round(self.cushions["bottom"], 1)
                },
                "pockets": [{
                    "id": p["id"],
                    "type": p["position"],
                    "position": [round(p["center"][0], 1), round(p["center"][1], 1)],
                    "diameter": round(p["radius"]*2, 1)
                } for p in self.pockets]
            },
            "balls_analysis": [{
                "id": name,
                "type": "cue" if name == self.cue_ball else "object",
                "position": [round(info["center"][0], 1), round(info["center"][1], 1)],
                "cue_relationship": {
                    "distance": round(self._distance_between(
                        self.balls[self.cue_ball]["center"],
                        info["center"]
                    ), 1),
                    "angle_to_pockets": [{
                        "pocket_id": pid,
                        "attack_angle": path_data["angle"],
                        "path_analysis": {
                            "cue_to_target": {
                                "distance": round(self._distance_between(
                                    self.balls[self.cue_ball]["center"],
                                    info["center"]
                                ), 1),
                                "blockers": path_data["blockers"]["cue_to_ball"]
                            },
                            "target_to_pocket": {
                                "distance": round(self._distance_between(
                                    info["center"],
                                    next(p["center"] for p in self.pockets if p["id"] == pid)
                                ), 1),
                                "blockers": path_data["blockers"]["ball_to_pocket"]
                            }
                        },
                        "clear_shot": not path_data["is_blocked"]
                    } for pid, path_data in analysis.get(name, {}).items()]
                },
                "position_risk": self._format_cushion_status_json(
                    self._check_cushion_contact(info["center"], info["radius"])
                )
            } for name, info in self.balls.items()]
        }

def _format_cushion_status_json(self, status: dict) -> dict:
    """Format the library status as JSON for analysis."""
    return {
        "contact_status": status["any"],
        "contact_sides": [k for k in ["left", "right", "top", "bottom"] if status[k]],
        "risk_level": "high" if status["any"] else "low"
    }


# Ensure the existence of the weight directory
def ensure_weights_dir():
    """make sure NineBallPocketNoNine/weights directory exists"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)  # 更新：获取项目根目录
    
    # 使用NineBallPocketNoNine/weights目录
    weight_dir = os.path.join(project_dir, "NineBallPocketNoNine", "weights")
    
    # if the directory does not exist, create it
    if not os.path.exists(weight_dir):
        os.makedirs(weight_dir, exist_ok=True)
        print(f"The weight directory has been created: {weight_dir}")
    
    # check if the weight files exist
    has_weights = False
    for weight_file in ["best.pt", "last.pt"]:
        if os.path.exists(os.path.join(weight_dir, weight_file)):
            has_weights = True
            break
    
    if not has_weights:
        print(f"Warning: The weight file was not found. Please place the weight file at {weight_dir}")
        print("The file name should be 'best.pt' or 'last.pt'.")

# Set the default source image
ensure_weights_dir()

if "BILLIARD_IMAGE_PATH" in os.environ:
    print(f"Use the pictures specified by the environment variables: {os.environ['BILLIARD_IMAGE_PATH']}")
    OPT.source = os.environ["BILLIARD_IMAGE_PATH"]
else:
    print(f"Use the default picture: {OPT.source}")
    
# If the weight file is specified in the environment variable, set it in OPT
if "YOLO_WEIGHT_PATH" in os.environ and os.path.exists(os.environ["YOLO_WEIGHT_PATH"]):
    print(f"Use the weight file specified by the environment variable: {os.environ['YOLO_WEIGHT_PATH']}")
    OPT.weights = os.environ["YOLO_WEIGHT_PATH"]

results = main(OPT)

has_detections = False
for result in results:
    if result.get('command') == 'no_target' or 'location' not in result:
        print("D")
        analysis_json = {
            "error": "no_detections",
            "message": "No billiards were detected. Please ensure that the image contains a clear billiards scene."
        }
        
        with open("billiard_analysis.json", "w", encoding="utf-8") as f:
            json.dump(analysis_json, f, indent=2)
            print("The JSON without detection results has been saved")
        break
    
    has_detections = True
    
    data = []
    counter = 0
    for loc, cls, conf in zip(result['location'], result['class'], result['confidence']):
        if int(cls) == 19:
            counter = counter + 1
            tempDict = {}
            tempDict["id"] = counter
            tempDict["bbox"] = list(map(int, loc))
            confidence = round(float(conf), 3)
            data.append(tempDict)

    analyzer = BilliardAngleAnalyzer(data)
    print(data)

    for loc, cls, conf in zip(result['location'], result['class'], result['confidence']):
        if int(cls) == 16:
            analyzer.register_ball({
                "name": "cue",
                "bbox": list(map(int, loc)),
                "type": "cue"})
        elif int(cls) == 0:
            analyzer.register_ball({
                "name": str(int(cls)+1),
                "bbox": list(map(int, loc))})
        elif int(cls) < 16:
            analyzer.register_ball({
                "name": str(int(cls)-5),
                "bbox": list(map(int, loc))})
            #print(str(int(cls)))

    print(analyzer.generate_report())

    analysis_json = analyzer.generate_analysis_json()

    with open("billiard_analysis.json", "w") as f:
        json.dump(analysis_json, f, indent=2)
        print("Analysis JSON saved to billiard_analysis.json")

    # print(json.dumps(analysis_json, indent=2))

if not has_detections and not os.path.exists("billiard_analysis.json"):
    analysis_json = {
        "error": "no_detections",
        "message": "No billiards were detected. Please ensure that the image contains a clear billiards scene"
    }
    
    with open("billiard_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis_json, f, indent=2)